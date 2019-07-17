from datetime import datetime, timedelta
import logging
from operator import itemgetter

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.encoding import force_text
from django.utils.formats import date_format
from django.utils.timezone import now as django_now, utc
from django.utils.translation import get_language, ugettext_lazy as _

from libya_elections.abstract import AbstractTimestampTrashBinModel, TrashBinManager
from libya_elections.libya_bread import BallotFormatterMixin, ElectionFormatterMixin, \
    ElectionTimesFormatterMixin, SubconstituenciesFormatterMixin, \
    StartEndTimeFormatterMixin
from libya_elections.utils import max_non_none_datetime, min_non_none_datetime, \
    find_overlapping_records, at_noon, at_midnight


logger = logging.getLogger(__name__)


class ElectionManager(TrashBinManager):
    def get_current_election(self, as_of=None):
        """Returns the election currently in progress (somewhere between the first and
        last things that are scheduled for it), or None if there is no such election.
        """
        as_of = as_of or django_now()
        return self.filter(
            start_time__lte=as_of,
            end_time__gt=as_of,
        ).order_by('start_time').first()

    def get_most_current_election(self, as_of=None):
        """Returns the 'most current' election, which is one of the following, in this order:
        1) The election currently in progress
        2) The next scheduled election
        3) The most recently completed election

        If none of the above exist, returns None.
        """
        election = self.get_election_in_progress(as_of)

        if not election:
            election = self.get_next_election(as_of)

        if not election:
            election = self.get_previous_election(as_of)

        return election

    def get_election_in_progress(self, as_of=None):
        """
        If there's an election with polling allowed right now,
        return the Election object.
        Else return None.
        """
        as_of = as_of or django_now()
        return self.filter(
            polling_start_time__lte=as_of,
            polling_end_time__gt=as_of,
        ).first()

    def get_next_election(self, as_of=None):
        """
        Return the nearest election that's not over, or None.
        """
        as_of = as_of or django_now()
        return (self.filter(polling_end_time__gt=as_of)
                .order_by('polling_end_time').first())

    def get_previous_election(self, as_of=None):
        """
        Return the most recently completed election, or None.
        """
        as_of = as_of or django_now()
        return (self.filter(polling_end_time__lte=as_of)
                .order_by('-polling_end_time').first())

    def get_elections_with_polling_reports_enabled(self, as_of=None):
        """
        The polling reporting period is from the time polling starts until 16 hours
        after polling ends, for in person elections only.
        """
        as_of = as_of or django_now()
        return self.filter(
            polling_start_time__lte=as_of,
            work_end_time__gt=as_of,
        )

    def get_elections_with_preliminary_vote_counts_enabled(self, as_of=None):
        """
        The preliminary vote count submitting period is the same as the polling
        reporting period, and also for in person elections only.
        """
        return self.get_elections_with_polling_reports_enabled(as_of)

    def get_elections_with_phone_activation_enabled(self, as_of=None):
        """
        People can activate phones to centers between midnight,
        two days before polling starts, and the end of
        polling, for in-person elections only.
        """
        as_of = as_of or django_now()
        return self.filter(
            work_start_time__lte=as_of,
            polling_end_time__gt=as_of,
        )

    def get_elections_with_center_opening_enabled(self, as_of=None):
        """
        People can report center opening between midnight,
        two days before polling starts, and the end of
        polling, for in-person elections only.
        """
        as_of = as_of or django_now()
        return self.filter(
            work_start_time__lte=as_of,
            polling_end_time__gt=as_of,
        )


class ReminderQueued(AbstractTimestampTrashBinModel):
    """
    Created when a particular reminder message for an election
    has been queued.
    """
    election = models.ForeignKey('voting.Election', verbose_name=_('election'),
                                 on_delete=models.CASCADE)
    message_number = models.IntegerField(_('message number'))
    reminder_number = models.IntegerField(_('reminder number'))

    class Meta(object):
        verbose_name = _("reminder queued")
        verbose_name_plural = _("reminders queued")
        # NB: there's a uniqueness constraint in the database, added
        # by migration 0002, like this but only applying to records with
        # deleted=False:
        # unique_together = ['election', 'message_number', 'reminder_number']


class Election(ElectionTimesFormatterMixin,
               AbstractTimestampTrashBinModel):
    name_english = models.CharField(_('name (English)'), max_length=150)
    name_arabic = models.CharField(_('name (Arabic)'), max_length=150)

    start_time = models.DateTimeField(
        _('start time'),
        help_text=_("Earliest time associated with this election - set automatically "
                    "from other fields"),
        blank=True, null=True,
        editable=False,
    )
    end_time = models.DateTimeField(
        _('end time'),
        help_text=_("Latest time associated with this election - set automatically "
                    "from other fields"),
        blank=True, null=True,
        editable=False,
    )

    polling_start_time = models.DateTimeField(_('polling start time'))
    polling_end_time = models.DateTimeField(_('polling end time'))

    work_start_time = models.DateTimeField(
        _('work start time'),
        help_text=_("Earliest time that phones can be activated, center opening reports "
                    "submitted, etc. for this election. Automatically set to midnight "
                    "two days before the start of polling."),
        editable=False,
        null=True,
        default=datetime(1970, 1, 1, tzinfo=utc)  # for ease of migrations
    )
    work_end_time = models.DateTimeField(
        _('work end time'),
        help_text=_("Latest time that reports can be submitted for this election. "
                    "Automatically set to 16 hours after the end of polling."),
        editable=False,
        null=True,
        default=datetime(1970, 1, 1, tzinfo=utc)
    )

    objects = ElectionManager()

    class Meta(object):
        verbose_name = _("election")
        verbose_name_plural = _("elections")
        ordering = ['polling_start_time']
        permissions = [
            ("browse_election", "Can list elections"),
            ("read_election", "Can read election"),
        ]

    def __str__(self):
        return _('{0.name_arabic} ({0.name_english})').format(self)

    @property
    def name(self):
        if get_language() == 'ar':
            return self.name_arabic
        return self.name_english

    def get_absolute_url(self):
        return reverse('read_election', args=[self.id])

    def clean(self):
        if self.polling_start_time and self.polling_end_time and \
           self.polling_start_time > self.polling_end_time:
            raise ValidationError(_("polling start time is later than end time."))

    def save(self, *args, **kwargs):
        """
        Set start and end times to the earliest and latest timestamp fields
        that are set, or None.
        NOTE: Update this code when we add more time fields
        """
        self.work_start_time = at_midnight(self.polling_start_time - timedelta(hours=48))
        self.work_end_time = self.polling_end_time + timedelta(hours=16)
        self.start_time = min_non_none_datetime(
            self.work_start_time,
            self.polling_start_time,
        )
        self.end_time = max_non_none_datetime(
            self.work_end_time,
            self.polling_end_time,
        )
        super(Election, self).save(*args, **kwargs)

    def polling_is_over(self):
        return self.polling_end_time <= django_now()

    def polling_is_in_progress(self):
        return self.polling_start_time <= django_now() < self.polling_end_time

    @property
    def num_candidates(self):
        return Candidate.objects.filter(ballot__election=self).count()

    def get_reminders(self):
        """
        Return a list of all the reminders that should be sent about this election.
        They are in date order.  The times are all computed from the start of polling.

        Each item is a dictionary with these fields:

        when: when the reminder should be sent (datetime)
        audience:  'whitelist' or 'registered'
        message_number: 1-7
        reminder_number: 1-3 for messages 1-6, 1-4 for message 7
          (if a recipient has already sent the report for a message,
          they are not sent reminders)
        sent: True if this reminder has been queued already
        """
        polling_start = self.polling_start_time

        # Messages 1-6, the times around which we'll schedule reminders, and who to send them to
        messages = {
            1: {'time': at_noon(polling_start - timedelta(hours=48)),
                'audience': 'whitelist'},
            2: {'time': at_noon(polling_start - timedelta(hours=24)),
                'audience': 'whitelist'},
            3: {'time': polling_start, 'audience': 'whitelist'},
            4: {'time': polling_start.replace(hour=12, minute=0), 'audience': 'registered'},
            5: {'time': polling_start.replace(hour=16, minute=0), 'audience': 'registered'},
            6: {'time': polling_start.replace(hour=20, minute=15), 'audience': 'registered'},
        }

        # Send reminders 30 minutes before, 5 minutes before, and 30 minutes after each
        # message time (for messages 1-6)
        reminder_offsets = {
            1: timedelta(minutes=-30),
            2: timedelta(minutes=-5),
            3: timedelta(minutes=30),
        }

        # Compute all the reminder times
        # reminder_time[message_number][reminder_number] is the reminder datetime
        reminder_time = {
            message_number: {
                reminder_number:
                    messages[message_number]['time'] + reminder_offsets[reminder_number]
                for reminder_number in sorted(reminder_offsets.keys())
            }
            for message_number in sorted(messages.keys())
        }
        # What tasks do we need to add?
        reminders = [
            {
                'when': reminder_time[message_number][reminder_number],
                'message_number': message_number,
                'reminder_number': reminder_number,
                'audience': messages[message_number]['audience']
            }
            for reminder_number in sorted(reminder_offsets.keys())
            for message_number in sorted(messages.keys())
        ]

        # Message 7 is kind of its own thing
        next_day = polling_start + timedelta(days=1)
        message_7_times = {
            1: polling_start.replace(hour=21, minute=30),
            2: polling_start.replace(hour=22, minute=30),
            3: polling_start.replace(hour=23, minute=30),
            4: next_day.replace(hour=8, minute=0),
        }

        message_number = 7
        reminders += [
            {
                'when': message_7_times[reminder_number],
                'message_number': message_number,
                'reminder_number': reminder_number,
                'audience': 'registered',
            }
            for reminder_number in sorted(message_7_times.keys())
        ]

        sent_already = set([
            (item.message_number, item.reminder_number)
            for item in ReminderQueued.objects.filter(election=self)])
        for reminder in reminders:
            key = (reminder['message_number'], reminder['reminder_number'])
            reminder['sent'] = key in sent_already

        return sorted(reminders, key=itemgetter('when'))

    def get_unsent_reminders(self):
        """Like get_reminders(), but only returns unsent ones"""
        return [reminder
                for reminder in self.get_reminders()
                if not reminder['sent']]

    def get_due_unsent_reminders(self, from_time, to_time):
        """
        Like get_reminders, but only returns unsent ones whose time
        is between the given from_time and to_time
        """
        return [reminder
                for reminder in self.get_unsent_reminders()
                if from_time <= reminder['when'] <= to_time]

    def schedule_due_reminders(self, from_time, to_time):
        for reminder in self.get_due_unsent_reminders(from_time, to_time):
            message_reminder_task.delay(
                reminder['message_number'],
                reminder['reminder_number'],
                reminder['audience'],
                self
            )
            ReminderQueued.objects.create(
                election=self,
                message_number=reminder['message_number'],
                reminder_number=reminder['reminder_number'],
            )


class Ballot(ElectionFormatterMixin, SubconstituenciesFormatterMixin,
             AbstractTimestampTrashBinModel):
    BALLOT_GENERAL = 0
    BALLOT_WOMENS = 1
    BALLOT_TYPE_CHOICES = [
        (BALLOT_GENERAL, _("General ballot")),
        (BALLOT_WOMENS, _("Women's ballot")),
    ]
    VALID_RACE_TYPES = [x[0] for x in BALLOT_TYPE_CHOICES]

    election = models.ForeignKey(Election, related_name='ballots', verbose_name=_('election'),
                                 on_delete=models.CASCADE)
    subconstituencies = models.ManyToManyField('register.SubConstituency', blank=True,
                                               verbose_name=_('subconstituencies'),
                                               related_name='ballots')
    internal_ballot_number = models.IntegerField(
        _('internal ballot number'),
        help_text=_("Number used internally to identify unique ballots across an election."),
    )
    ballot_type = models.IntegerField(_('ballot type'), choices=BALLOT_TYPE_CHOICES,
                                      default=BALLOT_GENERAL)
    num_seats = models.IntegerField(_('number of seats'), default=1)

    class Meta:
        verbose_name = _("ballot")
        verbose_name_plural = _("ballots")
        ordering = ['election', 'internal_ballot_number']
        permissions = (
            ("browse_ballot", "Can browse ballots"),
            ("read_ballot", "Can view ballot"),
        )
        unique_together = [
            ('election', 'internal_ballot_number'),
        ]

    def __str__(self):
        # self.id can be None when this object is in the process of being deleted, and invoking
        # an M2M manager when in that state will raise an error.
        # ref: https://github.com/hnec-vr/libya-elections/issues/831
        subconstituencies = self.subconstituency_ids_formatted if self.id else ''
        return (_('Ballot #{ballot_number} {ballot_name} in subconstituencies '
                  '{subconstituencies} on {election}').format(
                      ballot_number=self.ballot_number,
                      ballot_name=self.name,
                      subconstituencies=subconstituencies,
                      election=self.election))

    def get_absolute_url(self):
        return reverse('read_ballot', args=[self.id])

    @property
    def subconstituency_ids_formatted(self):
        return ', '.join([str(subconstituency.id) for subconstituency
                         in self.subconstituencies.all()])

    @property
    def ballot_number(self):
        """
        Number used in text messages when voting on this ballot.
        1 for general ballot, 2 for womens ballot"""
        return 1 + self.ballot_type

    @staticmethod
    def ballot_number_to_ballot_type(num):
        """
        Given the public ballot number (e.g. as sent in by a voter), return
        the internal code for the corresponding ballot type.
        """
        return num - 1

    @property
    def name(self):
        return force_text(self.get_ballot_type_display())


class Candidate(BallotFormatterMixin, AbstractTimestampTrashBinModel):
    name_english = models.CharField(_('name (English)'), max_length=150)
    name_arabic = models.CharField(_('name (Arabic)'), max_length=150)
    candidate_number = models.IntegerField(
        _('candidate number'),
        help_text=_("Number used in text messages when voting for this candidate"))
    ballot = models.ForeignKey(Ballot, related_name='candidates', verbose_name=_('ballot'),
                               on_delete=models.CASCADE)

    class Meta(object):
        verbose_name = _("candidate")
        verbose_name_plural = _("candidates")
        ordering = ['ballot', 'candidate_number']
        permissions = (
            ("read_candidate", "Can view candidate"),
            ("browse_candidate", "Can browse candidates"),
        )
        unique_together = [
            ('candidate_number', 'ballot'),
        ]

    def __str__(self):
        return _("Candidate {0.name_arabic} ({0.name_english}) on {0.ballot}").format(self)

    @property
    def election(self):
        # Used in the admin
        return self.ballot.election


class RegistrationPeriodManager(TrashBinManager):
    def in_progress(self, as_of=None):
        """return True if any registration period is in progress,
        as_of the specified datetime or right now."""
        as_of = as_of or django_now()
        qset = self.get_queryset()  # returns only undeleted records
        return qset.filter(start_time__lte=as_of, end_time__gt=as_of).exists()


class RegistrationPeriod(StartEndTimeFormatterMixin, AbstractTimestampTrashBinModel):
    """
    Represent one registration period
    """
    start_time = models.DateTimeField(_('start time'))
    end_time = models.DateTimeField(_('end time'))

    objects = RegistrationPeriodManager()

    class Meta:
        verbose_name = _("registration period")
        verbose_name_plural = _("registration periods")
        permissions = (
            ("read_registrationperiod", "Can view registration period"),
            ("browse_registrationperiod", "Can browse registration periods"),
        )

    def __str__(self):
        return _("registration period from {start_time} to {end_time}").format(
            start_time=date_format(self.start_time, 'SHORT_DATETIME_FORMAT'),
            end_time=date_format(self.end_time, 'SHORT_DATETIME_FORMAT'),
        )

    def clean(self):
        if not (self.end_time and self.start_time):
            raise ValidationError(_("Both start and end must be provided."))

        # Start time must be <= end time. (Allow empty period because a lot
        # of our tests don't bother creating a period with any duration.)
        if self.end_time < self.start_time:
            # Fib a little in the error message...
            raise ValidationError(_("End time must be after start time."))

        # No two registration periods may overlap
        queryset = type(self).objects.all()
        if self.pk:
            queryset = queryset.exclude(pk=self.pk)
        overlappers = find_overlapping_records(
            self.start_time,
            self.end_time,
            queryset,
            'start_time',
            'end_time',
        )

        if overlappers.exists():
            raise ValidationError(_("Other registration periods overlap this one."))


# This is at the end to avoid circular import problems while still
# allowing it to be mocked during testing
from bulk_sms.tasks import message_reminder_task  # noqa: E402
