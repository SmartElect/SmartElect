import datetime

from mock import patch
from pytz import timezone

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils.timezone import now

from libya_elections.utils import at_midnight
from .factories import BallotFactory, CandidateFactory, ElectionFactory, RegistrationPeriodFactory
from ..models import Election, RegistrationPeriod, ReminderQueued


class UnicodeMethodTest(TestCase):

    def test_election(self):
        self.assertTrue(str(ElectionFactory()))

    def test_candidate(self):
        self.assertTrue(str(CandidateFactory()))

    def test_ballot(self):
        self.assertTrue(str(BallotFactory()))


class CandidateTest(TestCase):
    def test_unique_numbers(self):
        # Candidate numbers are unique
        cand1 = CandidateFactory()
        with self.assertRaises(IntegrityError):
            CandidateFactory(candidate_number=cand1.candidate_number, ballot=cand1.ballot)


class ElectionTest(TestCase):
    def setUp(self):
        # Remove pre-loaded elections to not interfere with these tests
        Election.objects.all().delete()

    def test_dont_return_deleted_elections(self):
        yesterday = now() - datetime.timedelta(days=1)
        tomorrow = now() + datetime.timedelta(days=1)
        e = ElectionFactory(polling_start_time=yesterday,
                            polling_end_time=tomorrow,
                            )
        self.assertEqual(Election.objects.get_next_election(), e)
        e.deleted = True
        e.save()
        self.assertEqual(Election.objects.get_next_election(), None)

    def test_start_time(self):
        # Setting any of the start times and saving changes the `start_time` field
        tz = timezone(settings.TIME_ZONE)
        d1 = tz.localize(datetime.datetime(2014, 1, 1, 13, 2, 0))
        e = ElectionFactory(polling_start_time=d1)
        e = Election.objects.get(pk=e.pk)
        # The earliest time will be the work_start_time, which is on midnight,
        # 2 days before
        work_start = at_midnight(d1 - datetime.timedelta(days=2))
        self.assertEqual(work_start, e.work_start_time)
        self.assertEqual(work_start, e.start_time)
        d3 = tz.localize(datetime.datetime(2013, 12, 31, 1, 1))
        e.polling_start_time = d3
        e.save()
        e = Election.objects.get(pk=e.pk)
        work_start = at_midnight(d3 - datetime.timedelta(days=2))
        self.assertEqual(work_start, e.start_time)

    def test_end_time(self):
        # Setting any of the end times and saving changes the `end_time` field
        tz = timezone(settings.TIME_ZONE)
        d1 = tz.localize(datetime.datetime(2014, 1, 1, 13, 3, 0))
        e = ElectionFactory(polling_end_time=d1)
        e = Election.objects.get(pk=e.pk)
        work_end = e.polling_end_time + datetime.timedelta(hours=16)
        self.assertEqual(work_end, e.end_time)

    def test_next_election(self):
        self.assertIsNone(Election.objects.get_next_election())
        ElectionFactory(
            polling_start_time=now() - datetime.timedelta(days=1),
            polling_end_time=now() - datetime.timedelta(days=1),
        )
        self.assertIsNone(Election.objects.get_next_election())
        election2 = ElectionFactory(
            polling_start_time=now() + datetime.timedelta(days=1),
            polling_end_time=now() + datetime.timedelta(days=1),
        )
        self.assertEqual(election2, Election.objects.get_next_election())
        ElectionFactory(
            polling_start_time=now() + datetime.timedelta(days=2),
            polling_end_time=now() + datetime.timedelta(days=2),
        )
        self.assertEqual(election2, Election.objects.get_next_election())

    def test_previous_election(self):
        self.assertIsNone(Election.objects.get_previous_election())
        ElectionFactory(
            polling_start_time=now() + datetime.timedelta(days=1),
            polling_end_time=now() + datetime.timedelta(days=1),
        )
        self.assertIsNone(Election.objects.get_previous_election())
        election2 = ElectionFactory(
            polling_start_time=now() - datetime.timedelta(days=1),
            polling_end_time=now() - datetime.timedelta(days=1),
        )
        self.assertEqual(election2, Election.objects.get_previous_election())
        ElectionFactory(
            polling_start_time=now() - datetime.timedelta(days=2),
            polling_end_time=now() - datetime.timedelta(days=2),
        )
        self.assertEqual(election2, Election.objects.get_previous_election())

    def test_get_reminders(self):
        # Compute reminders for election
        start = now() - datetime.timedelta(days=1)
        end = now() + datetime.timedelta(days=1)
        election = ElectionFactory(
            polling_start_time=start,
            polling_end_time=end,
        )
        # Mark one "sent"
        ReminderQueued.objects.create(
            election=election,
            message_number=1,
            reminder_number=1,
        )
        reminders = election.get_reminders()
        self.assertEqual(6 * 3 + 4, len(reminders))  # Lots of reminders
        reminders = election.get_unsent_reminders()
        self.assertEqual(6 * 3 + 4 - 1, len(reminders))  # One fewer unsent reminder
        long_time_ago = start - datetime.timedelta(days=36500)
        long_time_from_now = end + datetime.timedelta(days=36500)
        # And the unsent ones are all "due" sometime in this range
        reminders = election.get_due_unsent_reminders(long_time_ago, long_time_from_now)
        self.assertEqual(6 * 3 + 4 - 1, len(reminders))  # One fewer unsent reminder
        # There should be no reminders due a long time ago.
        reminders = election.get_due_unsent_reminders(long_time_ago, long_time_ago)
        self.assertFalse(reminders)

    def test_schedule_due_reminders(self):
        # If polling starts right now, there should be a reminder
        # due around now too.
        polling_start_time = now()
        polling_end_time = now() + datetime.timedelta(days=1)
        election = ElectionFactory(
            polling_start_time=polling_start_time,
            polling_end_time=polling_end_time,
        )
        from_ = polling_start_time - datetime.timedelta(minutes=10)
        to = polling_start_time + datetime.timedelta(minutes=10)
        self.assertTrue(election.get_due_unsent_reminders(from_, to))
        self.assertFalse(ReminderQueued.objects.all().exists())
        with patch('voting.models.message_reminder_task') as mock_task:
            election.schedule_due_reminders(from_, to)
        mock_task.delay.assert_called()
        self.assertTrue(ReminderQueued.objects.all().exists())


class RegistrationPeriodManagerTest(TestCase):
    def test_no_periods(self):
        self.assertFalse(RegistrationPeriod.objects.in_progress())

    def test_period_past(self):
        RegistrationPeriodFactory(
            start_time=now() - datetime.timedelta(days=2),
            end_time=now() - datetime.timedelta(days=1),
        )
        self.assertFalse(RegistrationPeriod.objects.in_progress())

    def test_period_not_started(self):
        RegistrationPeriodFactory(
            start_time=now() + datetime.timedelta(days=1),
            end_time=now() + datetime.timedelta(days=2),
        )
        self.assertFalse(RegistrationPeriod.objects.in_progress())

    def test_between_periods(self):
        # Make sure our query doesn't mistake periods before and after the
        # current time as a period currently in progress
        RegistrationPeriodFactory(
            start_time=now() - datetime.timedelta(days=2),
            end_time=now() - datetime.timedelta(days=1),
        )
        RegistrationPeriodFactory(
            start_time=now() + datetime.timedelta(days=1),
            end_time=now() + datetime.timedelta(days=2),
        )
        self.assertFalse(RegistrationPeriod.objects.in_progress())

    def test_during_period(self):
        RegistrationPeriodFactory(
            start_time=now() - datetime.timedelta(days=1),
            end_time=now() + datetime.timedelta(days=2),
        )
        self.assertTrue(RegistrationPeriod.objects.in_progress())

    def test_at_start_time(self):
        # The period starts right at the start time
        start_time = now()
        RegistrationPeriodFactory(
            start_time=start_time,
            end_time=start_time + datetime.timedelta(days=1)
        )
        with patch('voting.models.django_now') as mock_now:
            mock_now.return_value = start_time
            self.assertTrue(RegistrationPeriod.objects.in_progress())

    def test_just_before_start_time(self):
        start_time = now()
        RegistrationPeriodFactory(
            start_time=start_time,
            end_time=start_time + datetime.timedelta(days=1)
        )
        with patch('voting.models.django_now') as mock_now:
            mock_now.return_value = start_time - datetime.timedelta(seconds=1)
            self.assertFalse(RegistrationPeriod.objects.in_progress())

    def test_just_before_end_time(self):
        end_time = now()
        RegistrationPeriodFactory(
            start_time=end_time - datetime.timedelta(days=1),
            end_time=end_time,
        )
        with patch('voting.models.django_now') as mock_now:
            mock_now.return_value = end_time - datetime.timedelta(seconds=1)
            self.assertTrue(RegistrationPeriod.objects.in_progress())

    def test_at_end_time(self):
        # The period extends up to, but not at, the end time.
        end_time = now()
        RegistrationPeriodFactory(
            start_time=end_time - datetime.timedelta(days=1),
            end_time=end_time,
        )
        with patch('voting.models.django_now') as mock_now:
            mock_now.return_value = end_time
            self.assertFalse(RegistrationPeriod.objects.in_progress())


class RegistrationPeriodCleanTest(TestCase):
    """Tests for the clean method of RegistrationPeriod, catching overlaps
        with existing RegistrationPeriods and negative durations."""
    def setUp(self):
        # Create an existing period.  Then we'll try creating
        # others around it.
        self.reg_period = RegistrationPeriodFactory(
            start_time=now() - datetime.timedelta(days=1),
            end_time=now() + datetime.timedelta(days=1),
        )

    def test_self(self):
        # A reg period shouldn't conflict with itself
        self.reg_period.full_clean()

    def should_work(self, start_time, end_time):
        """Create a RegistrationPeriod with the given start and end times
        and assert that it passes cleaning"""
        period = RegistrationPeriod(start_time=start_time, end_time=end_time)
        period.full_clean()

    def should_not_work(self, start_time, end_time):
        """Create a RegistrationPeriod with the given start and end times
        and assert that it does not pass cleaning"""
        period = RegistrationPeriod(start_time=start_time, end_time=end_time)
        with self.assertRaises(ValidationError):
            period.full_clean()

    def test_backwards_period(self):
        # End before start is not allowed
        self.should_not_work(
            start_time=self.reg_period.end_time + datetime.timedelta(days=10),
            end_time=self.reg_period.end_time + datetime.timedelta(days=9),
        )

    def test_empty_period(self):
        # Empty period is valid, though we don't advertise it
        self.should_work(
            start_time=self.reg_period.end_time + datetime.timedelta(days=10),
            end_time=self.reg_period.end_time + datetime.timedelta(days=10),
        )

    def test_completely_before(self):
        self.should_work(
            start_time=self.reg_period.start_time - datetime.timedelta(days=2),
            end_time=self.reg_period.start_time - datetime.timedelta(days=2),
        )

    def test_end_abuts_existing_start(self):
        # This should work too
        self.should_work(
            start_time=self.reg_period.start_time - datetime.timedelta(days=2),
            end_time=self.reg_period.start_time,
        )

    def test_ends_during(self):
        # New period ends during the existing period
        # This should NOT work
        self.should_not_work(
            start_time=self.reg_period.start_time - datetime.timedelta(days=2),
            end_time=self.reg_period.end_time - datetime.timedelta(seconds=1),
        )

    def test_starts_during(self):
        # New period starts during the existing period
        # This should not work
        self.should_not_work(
            start_time=self.reg_period.start_time + datetime.timedelta(seconds=1),
            end_time=self.reg_period.end_time + datetime.timedelta(days=1),
        )

    def test_start_abuts_existing_end(self):
        # This should work
        self.should_work(
            start_time=self.reg_period.end_time,
            end_time=self.reg_period.end_time + datetime.timedelta(days=1),
        )

    def test_starts_after_existing_end(self):
        # This should work
        self.should_work(
            start_time=self.reg_period.end_time + datetime.timedelta(seconds=1),
            end_time=self.reg_period.end_time + datetime.timedelta(days=1),
        )

    def test_starts_before_and_ends_after_existing(self):
        # New period encompasses existing period
        # This should not work
        self.should_not_work(
            start_time=self.reg_period.start_time - datetime.timedelta(seconds=1),
            end_time=self.reg_period.end_time + datetime.timedelta(days=1),
        )

    def test_starts_and_ends_within_existing(self):
        # new period is inside existing period
        # This should not work
        self.should_not_work(
            start_time=self.reg_period.start_time + datetime.timedelta(seconds=1),
            end_time=self.reg_period.end_time - datetime.timedelta(seconds=1),
        )

    def test_two_empty_periods_at_same_time(self):
        # Pathological case - two empty periods do not overlap,
        # even if they start and end at the same time
        RegistrationPeriod.objects.all().delete()
        time = now()
        RegistrationPeriodFactory(start_time=time, end_time=time)
        self.should_work(start_time=time, end_time=time)

    def test_two_nonempty_periods_at_same_time(self):
        # A period should conflict with another period at exactly
        # the same start and end times
        self.should_not_work(
            start_time=self.reg_period.start_time,
            end_time=self.reg_period.end_time,
        )

    def test_missing_times(self):
        # Missing periods should fail, but not cause 500 errors.
        self.should_not_work(
            start_time=None,
            end_time=None,
        )
        self.should_not_work(
            start_time=self.reg_period.start_time,
            end_time=None,
        )
        self.should_not_work(
            start_time=None,
            end_time=self.reg_period.end_time,
        )
