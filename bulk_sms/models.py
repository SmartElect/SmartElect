from __future__ import unicode_literals
import datetime
import random

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _, ugettext

from libya_elections.abstract import AbstractTimestampTrashBinModel, TrashBinManager
from libya_elections.libya_bread import RegistrationCenterFormatterMixin, CreatedByFormatterMixin, \
    ReviewedByFormatterMixin
from libya_elections.phone_numbers import PhoneNumberField
from polling_reports.models import StaffPhone
from register.models import Registration, SMS


class BatchManager(TrashBinManager):
    def get_next_batch(self):
        """Returns next the highest priority active batch that needs to be processed.
        If there aren't any approved batches in the queue waiting to be processed,
        then it returns None.
        """
        active_batches = self.get_queryset().filter(status=Batch.APPROVED)
        return active_batches.order_by('-priority').first()


class Batch(AbstractTimestampTrashBinModel):
    PENDING = 1
    APPROVED = 2
    REJECTED = 3
    COMPLETED = 4
    PROCESSING = 5
    UPLOADING = 6

    STATUS_CHOICES = (
        (UPLOADING, _('Uploading')),
        (PENDING, _('Pending Approval')),
        (APPROVED, _('Approved')),
        (REJECTED, _('Rejected')),
        (COMPLETED, _('Completed')),
        (PROCESSING, _('Processing')),
    )

    PRIORITY_BATCH = 0
    PRIORITY_TIME_CRITICAL = 100

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                   related_name='batches_created')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    related_name='batches_reviewed',
                                    null=True, blank=True)
    status = models.IntegerField(choices=STATUS_CHOICES, default=PENDING)
    errors = models.IntegerField(default=0)
    priority = models.IntegerField(default=PRIORITY_BATCH,
                                   help_text="Batches with higher priority are sent first")

    objects = BatchManager()

    class Meta:
        verbose_name = _("batch")
        verbose_name_plural = _("batches")

    def __unicode__(self):
        return self.name

    def time_remaining(self):
        """
        Return the approximate time required to send all unsent messages
        in this batch. Format of return value is a timedelta -> H:MM:SS

        Returns 0 if no messages remaining.
        """
        num_remaining = self.messages.unsent().count()
        if num_remaining:
            seconds_remaining = num_remaining / settings.BULKSMS_DEFAULT_MESSAGES_PER_SECOND
            if seconds_remaining < 1:
                # if less than 1s, just round up to 1s
                seconds_remaining = 1
            return datetime.timedelta(seconds=seconds_remaining)
        else:
            return 0

    def random_n_messages(self, n=10):
        """
        Get a pseudorandom list of `n` messages from this batch.
        If n > len(batch), return len(batch) messages.
        """
        # pick a random start point and then count off 'n' messages from there
        message_count = self.messages.unsent().count()
        max_start = n if n <= message_count else message_count
        start = random.randint(0, message_count - max_start)
        return self.messages.unsent()[start:start + n]

    def add_messages(self, generator):
        """
        Add messages to the batch.

        :param generator: Should yield (phone_number, message, from_shortcode) tuples
        """
        # Run bulk_create every 1000 messages
        NUM_TO_BULK_CREATE = 10000
        messages_to_create = []
        for phone_number, message, from_shortcode in generator:
            kwargs = dict(phone_number=phone_number, message=message)
            if from_shortcode:
                kwargs['from_shortcode'] = from_shortcode
            messages_to_create.append(BulkMessage(batch=self, **kwargs))
            if len(messages_to_create) == NUM_TO_BULK_CREATE:
                BulkMessage.objects.bulk_create(messages_to_create)
                messages_to_create = []
        # bulk_create any leftover messages
        if messages_to_create:
            BulkMessage.objects.bulk_create(messages_to_create)


class BulkMessageQuerySet(models.query.QuerySet):

    def active(self):
        """ Returns messages ordered by creation_date. """
        return self.order_by('creation_date')

    def unsent(self):
        """ Returns unsent messages ordered by creation_date. """
        return self.active().filter(sms=None)

    def sent(self):
        """ Returns sent messages ordered by creation_date. """
        return self.active().filter(sms__isnull=False)


class BulkMessageManager(TrashBinManager):
    """ BulkMessage manager to install our custom BulkMessageQuerySet """
    queryset = BulkMessageQuerySet

    def active(self):
        return self.get_queryset().active()

    def unsent(self):
        return self.get_queryset().unsent()

    def sent(self):
        return self.get_queryset().sent()


class BulkMessage(AbstractTimestampTrashBinModel):
    phone_number = PhoneNumberField(_('phone number'))
    from_shortcode = models.CharField(_('from shortcode'),
                                      max_length=5,
                                      default=settings.REGISTRATION_SHORT_CODE,
                                      help_text=_('What shortcode should this appear to be from?'))
    message = models.TextField(_('message'))
    batch = models.ForeignKey(Batch, related_name='messages', verbose_name=_('batch'))
    sms = models.OneToOneField(SMS, null=True, blank=True, verbose_name=_('sms'))

    objects = BulkMessageManager()

    class Meta:
        verbose_name = _("bulk message")
        verbose_name_plural = _("bulk messages")

    def __unicode__(self):
        return 'Message to %s from batch %s' % (self.phone_number, self.batch)

    def clean(self):
        if self.from_shortcode not in settings.SHORT_CODES:
            raise ValidationError(_('Invalid shortcode: Valid values are: {}').format(
                list(settings.SHORT_CODES)))


class Broadcast(CreatedByFormatterMixin, RegistrationCenterFormatterMixin,
                ReviewedByFormatterMixin, AbstractTimestampTrashBinModel):
    STAFF_ONLY = 'staff'
    SINGLE_CENTER = 'single_center'
    ALL_REGISTRANTS = 'all_centers'
    CUSTOM = 'custom'  # Only used internally, never presented to users as a choice

    CUSTOM_CHOICE = (CUSTOM, _("Custom"))

    # Minimum choices we'll offer to users.  We might add others
    # when constructing the form if it's appropriate.
    MINIMUM_AUDIENCE = (
        (STAFF_ONLY, _("Staff")),
        (SINGLE_CENTER, _("Registrants in a single center")),
        (ALL_REGISTRANTS, _("Registrants in the entire voter register")),
    )
    # All possible values, used to configure the database field but
    # not necessarily offered to users.  See the corresponding form.
    ALL_AUDIENCES = MINIMUM_AUDIENCE + (CUSTOM_CHOICE, )

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   related_name='broadcast_created', verbose_name=_('created by'))
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    related_name='broadcast_reviewed',
                                    verbose_name=_('reviewed by'))
    batch = models.OneToOneField(Batch, verbose_name=_('batch'))
    audience = models.CharField(_('audience'), max_length=20, choices=ALL_AUDIENCES,
                                default=STAFF_ONLY)
    center = models.ForeignKey('register.RegistrationCenter', null=True, blank=True,
                               verbose_name=_('registration center'))
    message = models.TextField(_('message'))

    def __unicode__(self):
        return self.message

    def get_absolute_url(self):
        return reverse('read_broadcast', args=[self.id])

    def get_messages(self):
        """Returns iterator that yields (phone_number, message, from_shortcode) tuples
        for each individual in the audience."""
        if self.audience == self.STAFF_ONLY:
            from_shortcode = settings.REPORTS_SHORT_CODE
        else:
            from_shortcode = None
        get_phone_numbers = getattr(self, 'get_numbers_for_%s' % self.audience)
        phone_numbers = get_phone_numbers()
        for number in phone_numbers:
            yield number, self.message, from_shortcode

    @staticmethod
    def get_numbers_for_all_centers():
        """Returns a list of all confirmed registrants' phone numbers"""
        registrations = Registration.objects.all()
        return registrations.values_list('sms__from_number', flat=True).distinct()

    def get_numbers_for_single_center(self):
        """Returns a list of all confirmed registrants' phone numbers in a single
        registration center."""
        registrations = Registration.objects.filter(registration_center=self.center)
        return registrations.values_list('sms__from_number', flat=True).distinct()

    @staticmethod
    def get_numbers_for_staff():
        """Returns a list of all staff members' phone numbers in the StaffPhone table."""
        return StaffPhone.objects.values_list('phone_number', flat=True).distinct()

    @property
    def status(self):
        """Returns the batch status or None."""
        if self.batch:
            return self.batch.get_status_display()

    def save(self, *args, **kwargs):
        try:
            batch = self.batch
        except Batch.DoesNotExist:
            # create a batch for this broadcast if none has been created
            batch = Batch.objects.create(
                name=self.get_audience_display(),
                description=self.message,
                created_by=self.created_by,
            )
            self.batch = batch
        self.batch.created_by = self.created_by
        self.batch.reviewed_by = self.reviewed_by
        self.batch.save()
        super(Broadcast, self).save(*args, **kwargs)

    def remaining_time(self):
        """Return time remaining on batch (for staff/admin template)"""
        return self.batch.time_remaining()

    def sent_to(self):
        """Return audience/recipients (for staff/admin template)"""
        audience_display = self.get_audience_display()
        if self.audience == self.SINGLE_CENTER and self.center:
            audience = ugettext("Registrants in Center")
            return "{0} {1}".format(audience, self.center.id)
        return audience_display

    @property
    def total_messages(self):
        """Return number of undeleted messages in the batch (for staff/admin template)"""
        return self.batch.messages.count()

    @property
    def sent(self):
        """Return number of sent messages in the batch (for staff/admin template)"""
        return self.batch.messages.sent().count()

    @property
    def errors(self):
        """Return number of errors that occurred while sending (for staff/admin template)"""
        return self.batch.errors

    @property
    def random_messages(self):
        """Return a random sampling of messages (for staff/admin template)

        The sampling is in the form of an HTML table ready to be added inline to a page.
        """
        msg = ""
        if self.batch:
            messages = self.batch.random_n_messages()
            ctx = {"messages": messages}
            msg = render_to_string("bulk_sms/random_messages.html", ctx).replace('\n', ' ')

        return mark_safe(msg.replace('\n', ' '))

    class Meta:
        verbose_name = _("broadcast")
        verbose_name_plural = _("broadcasts")
        permissions = (
            ("approve_broadcast", "Can approve broadcast messages"),
            ("read_broadcast", "Can view broadcast messages"),
            ("browse_broadcast", "Can browse broadcast messages"),
        )
        ordering = ['creation_date']
