from django.contrib.auth import get_user_model
from django.test import TestCase

from mock import patch

from bulk_sms.models import Batch
from bulk_sms.tasks import message_reminder_task, \
    CheckinReminderMessage, PollingDayReportReminderMessage
from polling_reports.models import StaffPhone, PollingReport, CenterOpen
from polling_reports.tests.factories import CenterOpenFactory, StaffPhoneFactory, \
    PollingReportFactory
from register.models import Whitelist
from libya_elections import constants
from register.tests.factories import WhitelistFactory
from voting.tests.factories import ElectionFactory


class PollingReportReminderMessageTest(TestCase):
    def test_get_phone_numbers_1_3(self):
        for message_number in range(1, 4):
            for reminder in range(1, 4):
                Whitelist.objects.all().update(deleted=True)
                CenterOpen.objects.all().update(deleted=True)

                msg = CheckinReminderMessage(message_number, reminder)
                # Should get no numbers
                numbers = list(msg.get_phone_numbers_to_send_to())
                self.assertEqual(0, len(numbers))

                # Now add a number to the whitelist, should get that number
                number = "9871"
                WhitelistFactory(phone_number=number)
                numbers = list(msg.get_phone_numbers_to_send_to())
                self.assertEqual(1, len(numbers))
                self.assertIn(number, [x[0] for x in numbers])

                # Now, pretend we've gotten the roll call
                # Should not get that number
                CenterOpenFactory(phone_number=number)
                numbers = list(msg.get_phone_numbers_to_send_to())
                self.assertEqual(0, len(numbers))

    def test_get_phone_numbers_4_7(self):
        for message_number in range(4, 8):
            for reminder in range(1, 4):
                StaffPhone.objects.all().update(deleted=True)
                PollingReport.objects.all().update(deleted=True)

                msg = PollingDayReportReminderMessage(message_number, reminder)
                # should be no numbers
                self.assertEqual(0, len(list(msg.get_phone_numbers_to_send_to())))
                # Now register a number
                StaffPhoneFactory(phone_number='9871')
                # should be 1 number
                self.assertEqual(1, len(list(msg.get_phone_numbers_to_send_to())))

                # have the phone send a checkin for this reporting period
                reporting_period = message_number - 3
                num_voters = 27
                PollingReportFactory(
                    phone_number='9871',
                    period_number=reporting_period,
                    num_voters=num_voters,
                )
                # should be no numbers
                self.assertEqual(0, len(list(msg.get_phone_numbers_to_send_to())))


class MessageReminderTaskTest(TestCase):
    def setUp(self):
        # Need a superuser
        get_user_model().objects.create_superuser(username="fred",
                                                  email="fred@bedrock.tv",
                                                  password="barney")
        self.election = ElectionFactory()

    def test_empty(self):
        # With valid arguments, should at least create a batch
        self.assertEqual(0, Batch.objects.count())
        message_reminder_task(1, 1, 'whitelist', self.election)
        batch = Batch.objects.get()
        # no messages
        self.assertEqual(0, batch.messages.count())
        self.assertEqual(Batch.APPROVED, batch.status)
        self.assertEqual(Batch.PRIORITY_TIME_CRITICAL, batch.priority)

    @patch('bulk_sms.tasks.PollingReportReminderMessage.get_phone_numbers_to_send_to')
    def test_with_numbers(self, mock_get_numbers):
        shortcode = None
        number_list = [("1", "message1", shortcode), ("22", "message2", shortcode)]
        mock_get_numbers.return_value = number_list
        self.assertEqual(0, Batch.objects.count())
        message_reminder_task(1, 1, 'whitelist', self.election)
        batch = Batch.objects.get()
        # 2 messages
        self.assertEqual(2, batch.messages.count())
        self.assertEqual(Batch.APPROVED, batch.status)
        self.assertEqual(Batch.PRIORITY_TIME_CRITICAL, batch.priority)

    def test_reminder_text(self):
        # add one number to the whitelist and the registered list
        WhitelistFactory(phone_number="9871")
        StaffPhoneFactory(phone_number='9871')

        # message_numbers 1, 2, 3 should return message REMINDER_CHECKIN (code=54)
        message_reminder_task(1, 1, 'whitelist', self.election)
        message_reminder_task(2, 1, 'whitelist', self.election)
        message_reminder_task(3, 1, 'whitelist', self.election)
        batches = Batch.objects.all()
        for batch in batches:
            # assert that proper message_code is in the outgoing text
            self.assertIn(str(constants.REMINDER_CHECKIN), batch.messages.get().message)
        Batch.objects.all().delete()

        # message_numbers 4 and 5 should return message REMINDER_REPORT (code=55)
        message_reminder_task(4, 1, 'registered', self.election)
        message_reminder_task(5, 1, 'registered', self.election)
        batches = Batch.objects.all()
        for batch in batches:
            self.assertIn(str(constants.REMINDER_REPORT), batch.messages.get().message)
        Batch.objects.all().delete()

        # message_number 6 should return message REMINDER_LAST_REPORT (code=56)
        message_reminder_task(6, 1, 'registered', self.election)
        batch = Batch.objects.get()
        self.assertIn(str(constants.REMINDER_LAST_REPORT), batch.messages.get().message)
        Batch.objects.all().delete()

        # message_number 7 should return message REMINDER_CLOSE (code=57)
        message_reminder_task(7, 1, 'registered', self.election)
        batch = Batch.objects.get()
        self.assertIn(str(constants.REMINDER_CLOSE), batch.messages.get().message)

    def test_reminder_numbers(self):
        # add one number to the whitelist
        WhitelistFactory(phone_number="9871")
        # reminder_number should be in the message
        reminder_number = 38
        message_reminder_task(2, reminder_number, 'whitelist', self.election)
        batch = Batch.objects.get()
        self.assertIn(str(reminder_number), batch.messages.get().message)
