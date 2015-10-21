from django.conf import settings
from django.contrib.auth.models import Group
from django.core.urlresolvers import reverse
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from libya_elections.abstract import AbstractTimestampTrashBinModel
from libya_elections.libya_bread import StartEndTimeFormatterMixin, TimestampFormatterMixin
from libya_elections.phone_numbers import FormattedPhoneNumberMixin, PhoneNumberField


BUTTON_GO_BACK = "goback"
BUTTON_START_OVER = "startover"
BUTTON_YES = "yes"
BUTTON_NO = "no"
BUTTON_NO_CITIZEN = "no_citizen"
BUTTON_MATCH = "match"
BUTTON_NO_MATCH = "nomatch"
BUTTON_CONTINUE = "continue"
BUTTON_HUNG_UP = "hungup"
BUTTON_SUBMIT = "submit"
BUTTON_UNABLE = "unable"
BUTTON_DONE = "done"

BUTTON_CHOICES = (
    (BUTTON_GO_BACK, _('Previous screen')),
    (BUTTON_START_OVER, _('Start from Beginning')),
    (BUTTON_YES, _('Yes')),
    (BUTTON_NO, _('No')),
    (BUTTON_NO_CITIZEN, _('No, Caller is a Citizen')),
    (BUTTON_MATCH, _('Name and ID match')),
    (BUTTON_NO_MATCH, _('Name and ID do not match')),
    (BUTTON_CONTINUE, _('Continue')),
    (BUTTON_HUNG_UP, _('Caller hung up')),
    (BUTTON_SUBMIT, _('Submit')),
    (BUTTON_UNABLE, _('Unable to Provide')),
    (BUTTON_DONE, _('Done')),
)
# To make it easier to look up the text for a button
BUTTON_TEXT = dict(BUTTON_CHOICES)

# CSS class to use for rendering each button, if not overridden by the screen.
DEFAULT_BUTTON_CLASSES = {
    BUTTON_GO_BACK: 'info',

    BUTTON_YES: 'success',   # BLUE
    BUTTON_MATCH: 'success',   # BLUE
    BUTTON_CONTINUE: 'success',   # BLUE
    BUTTON_SUBMIT: 'success',
    BUTTON_DONE: 'success',

    BUTTON_NO: 'warning',   # RED
    BUTTON_NO_CITIZEN: 'warning',  # RED
    BUTTON_UNABLE: 'warning',  # RED
    BUTTON_NO_MATCH: 'warning',  # RED

    BUTTON_HUNG_UP: 'inverse',  # BLACK
}

# Group names - for permissions
HELP_DESK_OPERATORS_GROUP = "Help Desk Operators"
HELP_DESK_SUPERVISORS_GROUP = "Help Desk Supervisors"
HELP_DESK_SENIOR_STAFF_GROUP = "Help Desk Senior Staff"
HELP_DESK_VIEW_GROUP = "Help Desk Viewers"
HELP_DESK_MANAGERS_GROUP = "Help Desk Managers"

# Permissions to give each group
# Operators are not quite a superset of the view-only permissions because operators
# don't necessarily need to be able to read the reports, I don't think.
# After that, though, each group contains the previous group's permissions,
# plus some new ones.
HELP_DESK_GROUP_PERMISSIONS = {
    HELP_DESK_VIEW_GROUP: [
        'help_desk.read_report',
        'help_desk.read_case',
    ],
    HELP_DESK_OPERATORS_GROUP: [
        'help_desk.add_case',
        'help_desk.change_case',
        'help_desk.read_case'
    ],
    HELP_DESK_SUPERVISORS_GROUP: [
        HELP_DESK_VIEW_GROUP,
        HELP_DESK_OPERATORS_GROUP,
        'help_desk.add_operator',
        'help_desk.add_update',
        'help_desk.cancel_registration_change',
        'help_desk.mark_case',
    ],
    HELP_DESK_SENIOR_STAFF_GROUP: [
        HELP_DESK_SUPERVISORS_GROUP,
        'help_desk.recommend_case',
    ],
    HELP_DESK_MANAGERS_GROUP: [
        HELP_DESK_SENIOR_STAFF_GROUP,
        'help_desk.browse_fieldstaff',

        'help_desk.read_fieldstaff',

        'help_desk.add_fieldstaff',
        'help_desk.add_senior_staff',
        'help_desk.add_supervisor',
        'help_desk.add_viewonly',

        'help_desk.change_fieldstaff',
        'help_desk.change_staff_password',

        'help_desk.resolve_case',
        'help_desk.suspend_fieldstaff',
    ],
}


def all_help_desk_groups():
    return list(Group.objects.filter(name__in=HELP_DESK_GROUP_PERMISSIONS.keys(),))

# 1. Citizen has complained about the service.
# Action: Mark as seen
#
# 2. Accidentally unlocked.
# Action: Re-lock or Ignore
#
# 3. Citizen changes their mind about unlocking.
# Action: Re-lock or Ignore
#
# 4. Phone call was harassing.
# Action: Mark as seen

REASONS_TO_MARK = (
    ('complaint', _('Person has complained about the service.')),
    ('accident', _('Accidentally unlocked.')),
    ('changed_mind', _('Person on the end of the phone changes their mind about unlocking.')),
    ('harassing', _('Phone call was harassing. ')),
    ('other', _('Other reason, see comments.')),
)


ALLOWED_ACTIONS = {
    'complaint': ['seen'],
    'accident': ['relock', 'ignore'],
    'changed_mind':  ['relock', 'ignore'],
    'harassing': ['seen'],
    'other': ['seen'],
}


CASE_ACTIONS = (
    ('seen', _('Mark as seen.')),
    ('relock', _('Re-lock.')),
    ('ignore', _('Ignore.')),
)


class FieldStaff(FormattedPhoneNumberMixin, AbstractTimestampTrashBinModel):
    # Note that field staff are not website "User"s.  Or if they are,
    # we don't know or care.
    name = models.CharField(_('name'), max_length=160, default='')
    staff_id = models.IntegerField(
        _('staff id'),
        unique=True,
        validators=[
            MinValueValidator(100),
            MaxValueValidator(999),
        ]
    )
    phone_number = PhoneNumberField(_('phone number'))
    suspended = models.BooleanField(_('suspended'), blank=True, default=False)

    class Meta:
        ordering = ['name', 'staff_id']
        verbose_name = _("field staff member")
        verbose_name_plural = _("field staff members")
        permissions = [
            ('browse_fieldstaff', _('Can browse field staff')),
            ('read_fieldstaff', _('Can read field staff')),
            ('suspend_fieldstaff', _('Can suspend field staff')),  # Custom
        ]

    def __unicode__(self):   # pragma: no cover
        return u'%s (%s)' % (self.name, self.formatted_phone_number())

    def get_absolute_url(self):
        return reverse('read_fieldstaff', args=[self.pk])


# Note: Choices are char fields instead of integers to make it easier
# for other applications to make use of the data in the database.

class Case(StartEndTimeFormatterMixin, AbstractTimestampTrashBinModel):
    # start and end time of the call
    start_time = models.DateTimeField(_('start time'), default=now)
    end_time = models.DateTimeField(_('end time'), null=True, blank=True)
    current_screen = models.ForeignKey(
        'help_desk.ScreenRecord', related_name='current_case', verbose_name=_('current screen'),
        null=True, blank=True,
        on_delete=models.SET_NULL,
    )

    # operator handling the call
    operator = models.ForeignKey(settings.AUTH_USER_MODEL,
                                 verbose_name=_('operator'),
                                 related_name='cases_as_operator')
    # field staff making the call
    field_staff = models.ForeignKey('FieldStaff', null=True, blank=True,
                                    verbose_name=_('field staff'),
                                    related_name='help_desk_cases',
                                    on_delete=models.PROTECT,
                                    )
    # citizen whose registration is being worked with
    citizen = models.ForeignKey('civil_registry.Citizen',
                                verbose_name=_('citizen'),
                                related_name='help_desk_cases',
                                on_delete=models.PROTECT,
                                # Nullable because when a call starts we don't know who
                                # it's for (and might never find out).
                                null=True, blank=True,
                                )

    @property
    def blocked(self):
        """Return True if there's a corresponding citizen and they're blocked from registering
        and voting"""
        return self.citizen and self.citizen.blocked

    #: whether user's changes on their registered phone have been increased
    changes_increased = models.BooleanField(_('changes increased'), default=False)

    registration = models.ForeignKey(
        'register.Registration', null=True, blank=True,
        help_text=_("Registration of citizen at time of call"),
        verbose_name=_('registration'),
        related_name='cases',
        on_delete=models.PROTECT,
    )

    # Classifications of a case, re: being reviewed
    NOT_MARKED = 'unmarked'
    FOR_REVIEW = 'marked'
    RECOMMENDED = 'recommended'
    RESOLVED = 'resolved'
    REVIEW_CLASSIFICATION_CHOICES = (
        (NOT_MARKED, _('Not marked for review')),
        (FOR_REVIEW, _('Marked for review')),
        (RECOMMENDED, _('Recommendation made')),
        (RESOLVED, _('Resolved')),
    )
    review_classification = models.CharField(
        _('review classification'),
        choices=REVIEW_CLASSIFICATION_CHOICES, max_length=12, default=NOT_MARKED
    )

    reason_marked = models.CharField(
        _('reason marked'),
        choices=REASONS_TO_MARK, max_length=14, default='', blank=True, null=False,
    )

    recommended_action = models.CharField(
        _('recommended action'),
        choices=CASE_ACTIONS,  max_length=6, default='', blank=True, null=False,
    )

    # Possible outcomes of a call
    HUNG_UP = 'hungup'
    INVALID_STAFF_ID = 'invalid_staff_id'
    INVALID_STAFF_NAME = 'invalid_staff_name'
    INVALID_STAFF_PHONE = 'invalid_staff_phone'
    INVALID_NID = 'invalid_nid'
    INVALID_NAME_DOB = 'invalid_name_dob'
    INVALID_FRN = 'invalid_frn'
    UNREGISTERED = 'unregistered'
    REGISTRATION_OKAY = 'registered'
    SAME_PHONE = 'same_phone'
    INCREASED_CHANGES = 'increased_changes'
    UNLOCKED = 'unlocked'
    RELOCKED = 'relocked'
    CALL_OUTCOME_CHOICES = (
        (HUNG_UP, _('Hung up')),
        (INVALID_STAFF_ID, _('Invalid staff ID')),
        (INVALID_STAFF_NAME, _('Wrong staff name')),
        (INVALID_STAFF_PHONE, _('Wrong staff phone')),
        (INVALID_NID, _('Invalid NID')),
        (INVALID_NAME_DOB, _('Invalid name or birth year')),
        (INVALID_FRN, _('Invalid FRN and mother\'s name')),
        (UNREGISTERED, _('Not registered')),
        (REGISTRATION_OKAY, _('No help needed')),
        (SAME_PHONE, _('No change')),
        (INCREASED_CHANGES, _('Increased changes')),
        (UNLOCKED, _('Unlocked')),
        (RELOCKED, _('Relocked')),
    )
    call_outcome = models.CharField(
        _('call outcome'),
        choices=CALL_OUTCOME_CHOICES, max_length=20, blank=True, null=True,
    )
    ALL_CALL_OUTCOMES = [x[0] for x in CALL_OUTCOME_CHOICES]

    class Meta:
        verbose_name = _("case")
        verbose_name_plural = _("cases")
        ordering = ['-start_time']
        # Run 'python manage.py update_permissions' if the permissions change. Django
        # only updates these during syncdb if it is creating a new table
        # for this model.
        permissions = (
            ('read_case', 'Can read case'),
            ('cancel_registration_change', 'Can cancel change period'),
            ('mark_case', 'Can mark case for review'),
            ('recommend_case', 'Can recomment action on case'),
            ('resolve_case', 'Can mark a case as resolved'),
            ('read_report', 'Can read reports'),
            ('add_operator', 'Can add operator'),
            ('add_supervisor', 'Can add supervisor'),
            ('add_senior_staff', 'Can add senior staff'),
            ('add_viewonly', 'Can add view-only users'),
            ('add_manager', 'Can add help desk managers'),
            ('change_staff_password', 'Can set password for help desk staff'),
        )

    def __unicode__(self):   # pragma: no cover
        x = _(u"Call started %(start_time)s. Operator %(operator)s. ") % \
            {'start_time': self.formatted_start_time,
             'operator': self.operator.get_full_name() or self.operator.username}
        if self.citizen:
            x += _(u"Citizen is %s. ") % unicode(self.citizen)
        if self.end_time:
            x += _(u"Call ended %s. ") % self.end_time
        return x

    def reset(self):
        """
        Operator wants to start the case over. Clear any data that was collected
        during the call so far.  Does not save.
        """
        self.current_screen = None
        self.field_staff = None
        self.citizen = None
        self.changes_increased = False
        self.registration = None
        self.review_classification = self.NOT_MARKED
        self.reason_marked = ''
        self.recommended_action = ''
        self.call_outcome = None
        self.screens.all().delete()
        self.updates.all().delete()

    def get_operator_url(self):
        from help_desk.screens import FIRST_SCREEN
        return reverse(self.current_screen.name if self.current_screen else FIRST_SCREEN,
                       args=[self.pk])

    def get_absolute_url(self):
        return reverse('case_detail', args=[self.pk])

    def start_screen(self, name):
        self.current_screen = ScreenRecord.objects.create(
            case=self,
            name=name,
        )
        self.save(update_fields=['current_screen'])

    @property
    def last_screen(self):
        """Return the last screen of this case"""
        try:
            return self.screens.order_by('-start_time')[0]
        except IndexError:
            return None

    @property
    def has_previous_screen(self):
        """We can only 'go back' if there was a screen before this one"""
        return self.screens.count() > 1

    def end(self):
        self.end_time = now()

    def increase_changes_if_needed(self):
        """
        If the citizen is out of changes, give them 3 more, and set outcome
        to INCREASED_CHANGES
        """
        if self.registration.change_count >= self.registration.max_changes:
            self.registration.max_changes = self.registration.change_count + 3
            self.registration.save()
            self.call_outcome = Case.INCREASED_CHANGES
            self.changes_increased = True
            self.save(update_fields=['call_outcome', 'changes_increased'])

    def registration_unlocked(self):
        return self.registration and self.registration.unlocked

    def unlock_registration(self):
        if self.registration:
            self.registration.unlocked_until = now() + settings.LENGTH_OF_REGISTRATION_UNLOCKING
            self.registration.save()

    def relock_registration(self):
        if self.registration_unlocked:
            self.registration.unlocked_until = None
            self.registration.save()
            if self.call_outcome == Case.UNLOCKED:
                self.call_outcome = Case.RELOCKED
                self.save()

    def is_under_review(self):
        return self.review_classification in [Case.FOR_REVIEW, Case.RECOMMENDED]

    def get_state(self):
        if self.review_classification in (Case.FOR_REVIEW, Case.RECOMMENDED):
            return self.get_review_classification_display()
        elif self.end_time:
            return _(u'Complete')
        else:
            return _(u'In progress')

    def get_length_in_seconds(self):
        """
        Return length of call in seconds as a float,
        or 0 if call has not ended.
        """
        if not self.end_time:
            return 0.0
        delta = self.end_time - self.start_time
        return delta.total_seconds()

    @property
    def field_staff_validated(self):
        """
        Returns True if the call is being made by a field staffer and their
        identity has been verified.
        """
        from .screens import CHECK_STAFF_NAME, CHECK_STAFF_PHONE

        # We must have a staff ID and both name and ID have been validated
        return all([
            self.field_staff is not None,
            ScreenRecord.objects.filter(
                case=self,
                name=CHECK_STAFF_NAME,
                button=BUTTON_MATCH
            ).exists(),
            ScreenRecord.objects.filter(
                case=self,
                name=CHECK_STAFF_PHONE,
                button=BUTTON_YES
            ).exists()
        ])

    @property
    def national_id_validated(self):
        """
        Returns True if we have a Citizen NID and the caller
        has provided a matching name & DOB
        """
        from .screens import CHECK_NAME_AND_DOB
        return all([
            self.citizen is not None,
            ScreenRecord.objects.filter(
                case=self,
                name=CHECK_NAME_AND_DOB,
                button=BUTTON_YES
            ).exists()
        ])


class ScreenRecord(AbstractTimestampTrashBinModel):
    """
    A record of each screen that was visited during the call,
    and the operator's input.
    """
    case = models.ForeignKey(Case, related_name='screens', on_delete=models.CASCADE)
    name = models.CharField("screen name", max_length=40)
    start_time = models.DateTimeField(default=now)
    end_time = models.DateTimeField(null=True, blank=True)
    button = models.CharField(
        help_text="Button the operator pressed to finish the screen",
        choices=BUTTON_CHOICES, max_length=10,
        blank=True,
    )
    input = models.CharField(
        help_text="Input field from screen",
        blank=True, default='',
        max_length=80,
    )

    class Meta:
        verbose_name = _("screen record")
        verbose_name_plural = _("screen records")

    def __unicode__(self):   # pragma: no cover
        return self.name

    def end(self, case, button=None, input=None):
        # 'case' is the Case object to update - because self.case might
        # be a different Python object than the one the caller is working with.
        self.button = button or ''
        self.input = input or ''
        self.end_time = now()
        self.save()
        case.current_screen = None
        case.save()


class Update(TimestampFormatterMixin, AbstractTimestampTrashBinModel):
    """
    An update records any time someone changes the case's state AFTER the
    call (marks it for review, adds a comment, recommends an action,
    etc.)
    """
    MARK_FOR_REVIEW = 'mark'
    COMMENT = 'comment'
    RECOMMEND = 'recommend'
    CANCEL = 'cancel'
    RESOLVE = 'resolve'
    UPDATE_KIND_CHOICES = (
        (COMMENT, _("Comment")),
        (MARK_FOR_REVIEW, _("Mark case for review")),
        (RECOMMEND, _("Recommend action on case")),
        (CANCEL, _("Cancel open re-registration period")),
        (RESOLVE, _("Mark case as resolved")),
    )

    case = models.ForeignKey(Case, verbose_name=_('case'), related_name='updates',
                             on_delete=models.CASCADE)
    kind = models.CharField(verbose_name=_('kind of update'),
                            choices=UPDATE_KIND_CHOICES, max_length=10, default=COMMENT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_('user'),
                             on_delete=models.PROTECT)
    timestamp = models.DateTimeField(_('timestamp'), default=now)
    reason_marked = models.CharField(
        _('reason marked'),
        choices=REASONS_TO_MARK, max_length=14, default='', blank=True, null=False,
    )
    recommended_action = models.CharField(
        _('recommended action'),
        choices=CASE_ACTIONS,  max_length=6, default='', blank=True, null=False,
    )
    comment = models.TextField(verbose_name=_('comment'), blank=True)

    class Meta:
        ordering = ['timestamp']
        verbose_name = _("update")
        verbose_name_plural = _("updates")

    def __unicode__(self):
        return u"%s %s" % (self.get_kind_display(), self.case)
