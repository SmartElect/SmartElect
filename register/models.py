from collections import OrderedDict
from decimal import Decimal
import logging

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.query import QuerySet
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import get_language, override, ugettext_noop, ugettext_lazy as _
from django.utils.encoding import force_text
from django.views.decorators.debug import sensitive_variables

from libya_elections.abstract import AbstractTimestampTrashBinModel, TrashBinManager, \
    AbstractArchivableTimestampTrashBinModel
from libya_elections.libya_bread import CitizenFormatterMixin, \
    ConstituencyFormatterMixin, InResponseToFormatterMixin, OfficeFormatterMixin, \
    RegistrationCenterFormatterMixin, SMSFormatterMixin, SubconstituencyFormatterMixin
from libya_elections.constants import CENTER_ID_MAX_INT_VALUE, CENTER_ID_MIN_INT_VALUE, INCOMING, \
    NO_NAMEDTHING, OUTGOING, SPLIT_CENTER_SUBCONSTITUENCY_ID
from libya_elections.phone_numbers import format_phone_number, formatted_phone_number_tag, \
    PhoneNumberField, FormattedPhoneNumberMixin
from libya_elections.utils import ensure_unique, NUM_LATLONG_DECIMAL_PLACES
from text_messages.utils import get_message


logger = logging.getLogger(__name__)


class PersonManager(TrashBinManager):
    def create_from_citizen(self, citizen):
        return self.create(citizen=citizen)


class Person(AbstractTimestampTrashBinModel):
    blocked = models.BooleanField(
        _('blocked'),
        default=False,
        help_text="Whether this person is blocked from registering and voting",
    )
    citizen = models.ForeignKey(
        'civil_registry.Citizen',
        help_text=_("Uniquely identifies a person, even across changes of national ID"),
        verbose_name=_('citizen'),
        on_delete=models.deletion.PROTECT,
    )

    objects = PersonManager()

    @sensitive_variables()
    def __str__(self):
        return str(self.citizen)

    def clean(self):
        ensure_unique(self._meta.model, self, 'citizen_id')

    def block(self):
        """
        Mark the citizen as blocked if they're not already, AND ALSO delete
        any current registrations from them.
        """
        self.blocked = True
        self.save()
        # Make sure they are not registered - blocking should also prevent them from voting
        # Any current records: delete
        for reg in Registration.objects.filter(citizen=self.citizen):
            reg.soft_delete()

    def unblock(self):
        self.blocked = False
        self.save()

    class Meta:
        permissions = (("read_person", "Can read person"),)
        verbose_name = _("person")
        verbose_name_plural = _("people")
        ordering = ['id']


class NamedThingQuerySet(QuerySet):
    pass


class NamedThingManager(TrashBinManager):
    queryset = NamedThingQuerySet


class NamedThing(AbstractTimestampTrashBinModel):
    """
    Abstract model for things like Office, Constituency, Subconstituency
    that have an ID and a name, possibly English and Arabic.
    """
    id = models.IntegerField(_('id'), primary_key=True)
    name_english = models.CharField(_('name (English)'), max_length=128)
    name_arabic = models.CharField(_('name (Arabic)'), max_length=128)

    class Meta:
        abstract = True
        ordering = ['id']

    def __str__(self):
        return '%s %s - %s' % (self._meta.verbose_name, self.id, self.name)

    @staticmethod
    def get_name_field_name():
        """
        Returns the name of the name field that has the name for the
        current language.
        """
        return 'name_arabic' if get_language() == 'ar' else 'name_english'

    @property
    def name(self):
        return getattr(self, type(self).get_name_field_name())

    def read_url_name(self):
        raise NotImplementedError

    def get_absolute_url(self):
        """
        Return the URL for this NamedThing. Requires that the child class implements read_url_name.
        """
        return reverse(self.read_url_name, args=[self.id, ])


class Office(NamedThing):
    REGION_NONE = 0
    REGION_WEST = 1
    REGION_SOUTH = 2
    REGION_EAST = 3
    REGION_NONE_NAME = ugettext_noop("No Region")
    REGION_WEST_NAME = ugettext_noop("West")
    REGION_SOUTH_NAME = ugettext_noop("South")
    REGION_EAST_NAME = ugettext_noop("East")
    REGION_CHOICES = (
        (REGION_NONE, REGION_NONE_NAME),
        (REGION_WEST, REGION_WEST_NAME),
        (REGION_SOUTH, REGION_SOUTH_NAME),
        (REGION_EAST, REGION_EAST_NAME),
    )
    ALL_REGIONS = [choice[0] for choice in REGION_CHOICES]
    REGION_NAMES = dict(REGION_CHOICES)

    region = models.IntegerField(_("region"), choices=REGION_CHOICES, default=0)

    objects = NamedThingManager()

    class Meta(NamedThing.Meta):
        verbose_name = _("office")
        verbose_name_plural = _("offices")
        permissions = (
            ("read_office", "Can read office"),
            ("browse_office", "Can browse offices"),
        )

    def region_name(self):
        return self.REGION_NAMES[self.region]

    @property
    def read_url_name(self):
        return 'read_office'


class Constituency(NamedThing):
    objects = NamedThingManager()

    class Meta(NamedThing.Meta):
        permissions = (
            ("read_constituency", "Can read constituency"),
            ("browse_constituency", "Can browse constituencies"),
        )
        verbose_name = _("constituency")
        verbose_name_plural = _("constituencies")

    @property
    def read_url_name(self):
        return 'read_constituency'


class SubConstituency(NamedThing):
    objects = NamedThingManager()

    class Meta(NamedThing.Meta):
        permissions = (
            ("read_subconstituency", "Can read subconstituency"),
            ("browse_subconstituency", "Can browse subconstituencies"),
        )
        verbose_name = _("subconstituency")
        verbose_name_plural = _("subconstituencies")

    @property
    def read_url_name(self):
        return 'read_subconstituency'


class RegistrationCenterQuerySet(QuerySet):
    pass


class RegistrationCenterManager(TrashBinManager):
    queryset = RegistrationCenterQuerySet

    def delete_all_copy_centers(self):
        return RegistrationCenter.objects.filter(copy_of__isnull=False).update(deleted=True)


class RegistrationCenter(ConstituencyFormatterMixin, OfficeFormatterMixin,
                         SubconstituencyFormatterMixin, AbstractTimestampTrashBinModel):
    class Types(object):
        """Constants and helpers for center types."""
        GENERAL = 1
        DISPLACED = 2
        OIL = 3
        DISABILITY = 4
        REVOLUTION = 5
        COPY = 6
        SPLIT = 7

        CHOICES = (
            (GENERAL, _("General")),
            (DISPLACED, _("Displaced")),
            (OIL, _("Oil")),
            (DISABILITY, _("Disability")),
            (REVOLUTION, _("Revolution")),
            (COPY, _("Copy")),
            (SPLIT, _("Split")),
        )
        ALL = [choice[0] for choice in CHOICES]

        # NAMES contains two dicts, one for Arabic and one for English. Each maps center type
        # constants to their corresponding text from CHOICES. e.g. NAMES['en'][OIL] = "Oil"
        NAMES = OrderedDict()
        for language_code in ('ar', 'en'):
            NAMES[language_code] = {}
            with override(language_code):
                NAMES[language_code] = {choice: force_text(choice_name) for choice, choice_name in
                                        CHOICES}

        # NAMES_REVERSED reverses NAMES. NAMES_REVERSED contains Arabic and English dicts that map
        # center type names to their corresponding constants.
        NAMES_REVERSED = {'ar': {value: key for key, value in NAMES['ar'].items()},
                          'en': {value: key for key, value in NAMES['en'].items()}}

        @classmethod
        def get_choices(klass, language_code):
            """Return a list of 2-tuples of (value, name) from CHOICES for the given language.

            The returned list has the same order as CHOICES.
            """
            return [(key, value) for key, value in klass.NAMES[language_code].items()]

    center_id = models.IntegerField(_('center id'), db_index=True,
                                    validators=[MinValueValidator(CENTER_ID_MIN_INT_VALUE),
                                                MaxValueValidator(CENTER_ID_MAX_INT_VALUE)])
    name = models.CharField(_('name'), max_length=255)
    office = models.ForeignKey(Office, default=NO_NAMEDTHING, verbose_name=_('office'),
                               on_delete=models.CASCADE)
    constituency = models.ForeignKey(Constituency, default=NO_NAMEDTHING,
                                     verbose_name=_('constituency'),
                                     on_delete=models.CASCADE)
    subconstituency = models.ForeignKey(SubConstituency, default=NO_NAMEDTHING,
                                        related_name="registration_centers",
                                        verbose_name=_('subconstituency'),
                                        on_delete=models.CASCADE)
    mahalla_name = models.CharField(_('mahalla name'), max_length=255, blank=True)
    village_name = models.CharField(_('village name'), max_length=255, blank=True)
    center_type = models.PositiveSmallIntegerField(_('type'), choices=Types.CHOICES,
                                                   default=Types.GENERAL)
    center_lat = models.DecimalField(_('latitude'), max_digits=11,
                                     decimal_places=NUM_LATLONG_DECIMAL_PLACES,
                                     blank=True, null=True,
                                     validators=[MaxValueValidator(Decimal('90.0')),
                                                 MinValueValidator(Decimal('-90.0'))])
    center_lon = models.DecimalField(_('longitude'), max_digits=11,
                                     decimal_places=NUM_LATLONG_DECIMAL_PLACES,
                                     blank=True, null=True,
                                     validators=[MaxValueValidator(Decimal('180.0')),
                                                 MinValueValidator(Decimal('-180.0'))])

    # copy_of is populated only for copy centers and indicates the original center of which this
    # is a copy.
    copy_of = models.ForeignKey("self", null=True, blank=True, default=None,
                                related_name='copied_by', verbose_name=_('copy of'),
                                on_delete=models.CASCADE)

    # reg_open represents whether or not a center can have registrations.
    # A center which has reg_open==False won't have any registrations counted in
    # the reporting API and registration dashboard and won't be used by rollgen.
    # (Centers which are not open for polling should be recorded in the
    # CenterClosedForElection table.)
    reg_open = models.BooleanField(_("support for registrations"), default=True)

    objects = RegistrationCenterManager()

    def __str__(self):
        return "%s %s" % (self.center_id, self.name)

    def get_absolute_url(self):
        return reverse('read_registrationcenter', args=[self.id])

    def clean(self):
        ensure_unique(self._meta.model, self, 'center_id')

        if self.is_copy and (self.center_type != self.Types.COPY):
            raise ValidationError(_('Copy centre type must be "copy".'))

        if self.id:
            # For existing centers, copy status can't be changed. Once a copy center, always a
            # copy center, and ditto for non-copy centers. Ne'er the twain shall meet.
            # Note that we have to search through all centers (including deleted ones) to allow
            # undeleting.
            # In addition, copy centers are not editable.
            center = RegistrationCenter.objects.unfiltered().get(pk=self.id)
            if center.is_copy:
                raise ValidationError(_('Copy centres are read-only.'))

            # The check above ensures the user can't change the type *from* copy. We also need
            # to check that the type is not being changed *to* copy.
            if self.center_type == RegistrationCenter.Types.COPY:
                raise ValidationError(_('A centre may not be changed to a copy centre.'))
        else:
            # New centers can become copy centers
            if self.is_copy:
                if self.copy_of.copy_of:
                    raise ValidationError(_("A copy centre cannot copy another copy centre."))

                # Ensure that the original doesn't already have the max # of copies.
                if len(self.copy_of.copied_by.all()) == settings.N_MAX_COPY_CENTERS:
                    msg = _('Copy centre already has the maximum number of copies ({n_max}).')
                    raise ValidationError(msg.format(n_max=settings.N_MAX_COPY_CENTERS))
            else:
                if self.center_type == self.Types.COPY:
                    msg = _('Centre type "copy" requires copy centre information.')
                    raise ValidationError(msg)

        if ((self.center_lat is None and self.center_lon is not None)
                or (self.center_lon is None and self.center_lat is not None)):
            raise ValidationError(_("Either set both latitude and longitude or neither."))

        if self.center_type == self.Types.SPLIT:
            if self.subconstituency.id != SPLIT_CENTER_SUBCONSTITUENCY_ID:
                msg = _("Split centers must be associated with subconstituency {}.")
                msg = msg.format(SPLIT_CENTER_SUBCONSTITUENCY_ID)
                raise ValidationError(msg)
        else:
            if self.subconstituency.id == SPLIT_CENTER_SUBCONSTITUENCY_ID:
                msg = _("Only split centers may be associated with subconstituency {}.")
                msg = msg.format(SPLIT_CENTER_SUBCONSTITUENCY_ID)
                raise ValidationError(msg)

    class Meta:
        verbose_name = _("registration center")
        verbose_name_plural = _("registration centers")
        permissions = (
            ("read_registrationcenter", "Can view registration center"),
            ("browse_registrationcenter", "Can browse registration centers"),
        )
        ordering = ['center_id']

    @property
    def is_copy(self):
        """Return True if this is a copy center, False otherwise."""
        return bool(self.copy_of)

    @property
    def has_copy(self):
        """Return True if at least one other center copies this one, False otherwise."""
        return self.copied_by.all().exists()

    @property
    def office_name(self):
        return self.office.name if self.office else ''

    @property
    def region_name(self):
        return self.office.get_region_display() if self.office else ''

    @property
    def constituency_name(self):
        return self.constituency.name if self.constituency else ''

    @property
    def subconstituency_name(self):
        return self.subconstituency.name if self.subconstituency else ''

    @property
    def center_type_label(self):
        return self.get_center_type_display()

    def all_related_by_copy(self):
        """Return a list all centers related to this one via copy_of and copied_by.

        The return is a list of original + copies where original is the real center and copies is
        a list of the centers that are copies of the original. The original is always first in
        the returned list and the copies are sorted by center id.

        All centers returned by this method should themselves return the same centers. In other
        words, this will not fail:

        related = a_center.all_related_by_copy()
        for center in related:
            assert(related == center.all_related_by_copy())

        If the center is neither a copy of nor copied by another center, the method returns [self].
        This is a small convenience for callers that want all equivalent centers but don't care
        whether or not a center is a copy center. They can use this method without first testing
        center.is_copy.
        """
        original = self
        copies = []

        copied_by = list(self.copied_by.all())

        if self.copy_of:
            # This is a copy.
            original = self.copy_of
            copies = list(original.copied_by.all())
        elif copied_by:
            # This is an original
            copies = copied_by

        return [original] + copies


class Registration(CitizenFormatterMixin, RegistrationCenterFormatterMixin, SMSFormatterMixin,
                   AbstractArchivableTimestampTrashBinModel):

    # NB: We've added a partial index in Postgres to enforce unique citizens in
    # among Registrations with archive_time=None and deleted=False
    citizen = models.ForeignKey('civil_registry.Citizen', related_name="registrations",
                                verbose_name=_('citizen'),
                                on_delete=models.CASCADE)
    registration_center = models.ForeignKey('RegistrationCenter',
                                            verbose_name=_('registration center'),
                                            on_delete=models.CASCADE)
    sms = models.ForeignKey('SMS', verbose_name=_('sms'), related_name='registrations', null=True,
                            on_delete=models.CASCADE)
    change_count = models.IntegerField(
        _('change count'),
        default=0,
        help_text=_("The number of times this registration has been changed after "
                    "it was initially made (original registration not counted). ")
    )
    max_changes = models.IntegerField(
        _('max changes'),
        default=3,
        help_text=_("The number of times this registration is allowed to be changed "
                    "after it was initially made. Defaults to 3, but can be increased.")
    )
    repeat_count = models.IntegerField(
        _('repeat count'),
        default=1,
        help_text=_("The number of times messages have been received for "
                    "this exact registration. The first message is counted, "
                    "so the 2nd time we see the same registration, the count "
                    "becomes 2, and so forth. "
                    "This is reset each time the registration is changed.")
    )
    unlocked_until = models.DateTimeField(
        _('unlocked until'),
        blank=True, null=True,
        help_text=_("If this is set and the current datetime is earlier than this value, "
                    "allow changing this registration from any phone, even if it's not the "
                    "phone previously used.")
    )

    @sensitive_variables()
    def __str__(self):
        return "Registration for: %s" % self.citizen

    class Meta:
        verbose_name = _("registration")
        verbose_name_plural = _("registrations")
        permissions = (
            ("read_registration", "Can read registration"),
            ("browse_registration", "Can browse registration"),
        )
        ordering = ['-creation_date']

    def clean(self):
        """Give nicer error than a database integrity error on an attempt to create
        a duplicate confirmed registration"""
        if not self.archive_time:
            ensure_unique(self._meta.model, self, 'citizen', archive_time=None)

    @property
    def remaining_changes(self):
        return self.max_changes - self.change_count

    @property
    def unlocked(self):
        return self.unlocked_until and now() < self.unlocked_until

    @property
    def phone_has_maximum_registrations(self):
        """Return True if the phone used for this registration is at or over the
        maximum registrations per phone"""
        # For convenience from templates
        from register.utils import remaining_registrations
        if self.sms:
            return remaining_registrations(self.sms.from_number) == 0
        return False

    @property
    def formatted_unlocked_until(self):
        if self.unlocked_until:
            return _('This registration is unlocked until {}.'.format(self.unlocked_until))
        else:
            return _('This registration is locked.')


class SMSQuerySet(QuerySet):
    def anonymize(self):
        """Anonymize the selected SMSes - don't forget to get responses too"""
        num_changes = self.filter(direction=INCOMING).update(
            need_to_anonymize=False,
            uuid='',
            from_number='',
            message='',
            citizen=None
        )
        num_changes += self.filter(direction=OUTGOING).update(
            need_to_anonymize=False,
            uuid='',
            to_number='',
            message='',
            citizen=None
        )
        return num_changes


class SMSManager(TrashBinManager):
    queryset = SMSQuerySet


class SMS(CitizenFormatterMixin, InResponseToFormatterMixin, AbstractTimestampTrashBinModel):
    # Message type
    REGISTRATION = 3
    INVALID_FORMAT = 5
    MULTIPLE_PROBLEMS = 6
    INVALID_CENTRE_CODE_LENGTH = 7
    INVALID_CENTRE_CODE = 8
    INVALID_NID_LENGTH = 9
    INVALID_NID = 11
    UNKNOWN = 13
    UPDATE = 14
    QUERY = 15
    INVALID_FORM_LENGTH = 16
    ACTIVATE = 17
    DAILY_REPORT = 18
    DAILY_REPORT_INVALID = 19
    BULK_OUTGOING_MESSAGE = 20
    POLLING_REPORT = 21
    POLLING_REPORT_INVALID = 22
    NOT_ACTIVATED = 23
    NOT_HANDLED = 24

    DIRECTION_CHOICES = (
        (INCOMING, "Incoming"),
        (OUTGOING, "Outgoing"),
    )
    DIRECTIONS_MAP = {k: v for k, v in DIRECTION_CHOICES}

    # The reporting API needs to store the untranslated form of the message type
    # strings, so just mark them for the benefit of makemessages.
    MESSAGE_TYPES = (
        (REGISTRATION, _("Registration")),
        (INVALID_FORMAT, _("Invalid format")),
        (MULTIPLE_PROBLEMS, _("Multiple problems")),
        (INVALID_CENTRE_CODE_LENGTH, _("Invalid registration centre code length")),
        (INVALID_CENTRE_CODE, _("No such registration centre found")),
        (INVALID_NID_LENGTH, _("Not enough enough National ID digits")),
        (INVALID_NID, _("Invalid valid National ID")),
        (UNKNOWN, _("Unknown")),  # We haven't decided yet
        (UPDATE, _("Registration update")),
        (QUERY, _("Registration Center query")),
        (INVALID_FORM_LENGTH, _("Invalid Form ID")),
        (ACTIVATE, _("Phone activation")),
        (DAILY_REPORT, _("Daily Report")),
        (DAILY_REPORT_INVALID, _("Daily Report invalid")),
        (BULK_OUTGOING_MESSAGE, _("Bulk Outgoing Message")),
        (POLLING_REPORT, _("Polling Report")),
        (POLLING_REPORT_INVALID, _("Polling Report invalid")),
        (NOT_ACTIVATED, _("Phone number not activated")),
    )
    MESSAGE_TYPES_MAP = {k: v for k, v in MESSAGE_TYPES}

    from_number = models.CharField(_('from number'), max_length=15, db_index=True)
    to_number = models.CharField(_('to number'), max_length=15, db_index=True)
    citizen = models.ForeignKey('civil_registry.Citizen', null=True, blank=True,
                                related_name="messages", verbose_name=_('citizen'),
                                on_delete=models.CASCADE)
    carrier = models.ForeignKey('rapidsms.Backend', verbose_name=_('carrier'),
                                on_delete=models.CASCADE)
    direction = models.IntegerField(_('direction'), choices=DIRECTION_CHOICES, db_index=True)
    msg_type = models.IntegerField(_('message type'), choices=MESSAGE_TYPES)
    order = models.IntegerField(_('order'), null=True, blank=True)
    message = models.TextField(_('message'), db_index=True)
    message_code = models.IntegerField(
        _('message code'),
        default=0,  # there is no message 0
        help_text="If we're sending one of our canned messages, this is the message code.",
        db_index=True,
    )
    uuid = models.CharField(_('uuid'), blank=True, max_length=50, db_index=True)
    is_audited = models.BooleanField(_('is audited'), default=False, db_index=True)
    in_response_to = models.ForeignKey('SMS', null=True, blank=True, related_name='responses',
                                       verbose_name=_('in response to'),
                                       on_delete=models.CASCADE)
    need_to_anonymize = models.BooleanField(_('need to anonymize'), default=False, db_index=True)

    objects = SMSManager()

    @sensitive_variables()
    def __str__(self):
        return _("From {from_addr} to {to_addr}: {content}").format(
            from_addr=self.from_number_formatted,
            to_addr=self.to_number_formatted,
            content=self.message
        )

    class Meta(object):
        verbose_name = _("sms")
        # Translators: "smses" is plural for "SMS" (a Short Message Service text message)
        verbose_name_plural = _("smses")
        permissions = (
            ("read_sms", "Can read sms"),
            ("browse_sms", "Can browse sms"),
        )
        ordering = ['-creation_date']

    @property
    def from_number_formatted(self):
        return format_phone_number(self.from_number)

    @property
    def from_number_formatted_tag(self):
        return formatted_phone_number_tag(self.from_number)

    @property
    def to_number_formatted(self):
        return format_phone_number(self.to_number)

    @property
    def to_number_formatted_tag(self):
        return formatted_phone_number_tag(self.to_number)

    @property
    def direction_formatted(self):
        return self.DIRECTIONS_MAP[self.direction]

    @property
    def msg_type_formatted(self):
        return self.MESSAGE_TYPES_MAP[self.msg_type]

    def get_message_code_display(self):
        try:
            m = get_message(self.message_code)
        except ValueError:
            return _("Obsolete message code: {}").format(self.message_code)
        return m.label

    def get_absolute_url(self):
        return reverse('read_sms', args=[self.id])


class Blacklist(FormattedPhoneNumberMixin, AbstractTimestampTrashBinModel):
    phone_number = PhoneNumberField(_('phone number'), db_index=True)

    def __str__(self):
        return self.formatted_phone_number()

    def clean(self):
        ensure_unique(self._meta.model, self, 'phone_number')

    class Meta:
        verbose_name = _("blacklisted number")
        verbose_name_plural = _("blacklisted numbers")
        permissions = (
            ("read_blacklist", "Can read black list"),
            ("browse_blacklist", "Can browse black list"),
        )
        ordering = ['phone_number']


class Whitelist(FormattedPhoneNumberMixin, AbstractTimestampTrashBinModel):
    phone_number = PhoneNumberField(_('phone number'), db_index=True)

    def __str__(self):
        return self.formatted_phone_number()

    def clean(self):
        ensure_unique(self._meta.model, self, 'phone_number')

    class Meta:
        verbose_name = _("whitelisted number")
        verbose_name_plural = _("whitelisted numbers")
        permissions = (
            ("read_whitelist", "Can read whitelist"),
            ("browse_whitelist", "Can browse whitelist"),
        )
        ordering = ['phone_number']


# Signals
@receiver([post_save, pre_delete], sender=Blacklist)
def flush_blacklist_cache(sender, **kwargs):
    cache.delete('blacklist')


@receiver([post_save, pre_delete], sender=Whitelist)
def flush_whitelist_object_from_cache(sender, **kwargs):
    instance = kwargs['instance']
    cache.delete('whitelist:%s' % instance.phone_number)
