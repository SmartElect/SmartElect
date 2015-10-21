"""
These tests are organized, quite deliberately, to parallel the
logic as documented in the file LibyanVoterRegistration-PollingReportLogic.rst.

Please keep them that way.
"""
from datetime import timedelta
from django.conf import settings
from django.utils.timezone import now
from django.utils.translation import override
from mock import patch
from factory import create_batch
from libya_elections.constants import PHONE_NOT_ACTIVATED, NOT_WHITELISTED_NUMBER, \
    POLLING_REPORT_CENTER_MISMATCH, INVALID_CENTER_ID, PHONE_ACTIVATED, POLLING_REPORT_INVALID, \
    POLLING_NOT_OPEN, POLLING_REPORT_RECEIVED, CENTER_OPENING_NOT_AUTHORIZED, \
    PRELIMINARY_VOTES_REPORT, CENTER_OPENED, CENTER_OPEN_INDICATOR, FIRST_PERIOD_NUMBER, \
    LAST_PERIOD_NUMBER, POLLING_REPORT_RECEIVED_VERY_HIGH_TURNOUT, \
    POLLING_REPORT_RECEIVED_NO_REGISTRANTS, RESPONSE_SERVER_ERROR
from libya_elections.phone_numbers import get_random_phone_number
from polling_reports.handlers import ReportsShortCodeHandler
from polling_reports.models import StaffPhone, PollingReport, CenterOpen, PreliminaryVoteCount
from register.models import Whitelist, Registration, SMS
from register.tests.base import LibyaRapidTest
from register.tests.factories import WhitelistFactory, RegistrationCenterFactory, \
    RegistrationFactory
from text_messages.models import MessageText

from text_messages.utils import get_message
from voting.tests.factories import ElectionFactory


DONT_CARE = object()  # Unique object used to indicate a don't-care condition in the tests


def get_message_label(message_code):
    """Return the message label of the message with the given code"""
    return MessageText.objects.get(number=message_code).label


class PollingReportLogicTestCase(LibyaRapidTest):
    def setUp(self):
        self.NUMBER = get_random_phone_number()
        # Most tests need the number whitelisted, so whitelist by default
        WhitelistFactory(phone_number=self.NUMBER)
        self.election = ElectionFactory(
            polling_start_time=now() - timedelta(hours=1),
            polling_end_time=now() + timedelta(hours=1),
        )

    def check_it_out(self,
                     message,
                     expected_response_code,
                     expected_msg_type,
                     expect_phone_activated,
                     expect_report_saved,
                     expect_center_opened,
                     expect_votes_saved=DONT_CARE,
                     # change the test environment:
                     activation_center_opening_period=True,
                     polling_report_period=True,
                     ):
        """
        "Send" the message and see if the response and side effects are what we expect.
        """
        conn = self.lookup_connections(identities=[self.NUMBER])[0]
        self.assertEqual(self.NUMBER, conn.identity)
        fields = {'to_addr': settings.REPORTS_SHORT_CODE,
                  'from_addr': conn.identity}

        # These names are getting way long...
        opening_enabled_function = \
            'polling_reports.handlers.center_opening_enabled'
        with patch('polling_reports.handlers.polling_reports_enabled') as pr_enabled, \
                patch(opening_enabled_function) as ce_enabled:
            ce_enabled.return_value = activation_center_opening_period
            pr_enabled.return_value = polling_report_period
            self.receive(message, conn, fields=fields)

        actual_response_code = self.get_last_response_code()
        actual_msg_type = self.get_last_response().sms.msg_type

        if expected_response_code not in (DONT_CARE, actual_response_code):
            expected_label = get_message_label(expected_response_code)
            actual_label = get_message_label(actual_response_code)
            self.fail("Expected response code was %s (%s), got %s (%s)" %
                      (expected_response_code, expected_label,
                       actual_response_code, actual_label))
        if expected_msg_type not in (DONT_CARE, actual_msg_type):
            self.fail("Expected msg_type was %s, got %s" % (expected_msg_type, actual_msg_type))
        if expect_phone_activated is not DONT_CARE:
            exists = StaffPhone.objects.filter(phone_number=self.NUMBER).exists()
            if expect_phone_activated:
                self.assertTrue(exists)
            else:
                self.assertFalse(exists)
        if expect_report_saved is not DONT_CARE:
            exists = PollingReport.objects.all().exists()
            if expect_report_saved:
                self.assertTrue(exists)
            else:
                self.assertFalse(exists)
        if expect_center_opened is not DONT_CARE:
            exists = CenterOpen.objects.all().exists()
            if expect_center_opened:
                self.assertTrue(exists)
            else:
                self.assertFalse(exists)
        if expect_votes_saved is not DONT_CARE:
            exists = PreliminaryVoteCount.objects.all().exists()
            if expect_votes_saved:
                self.assertTrue(exists)
            else:
                self.assertFalse(exists)

        # Also test that the message came back in Arabic, just to be safe,
        # by getting the code's message in arabic. Just look at the part up
        # to the first replaceable parameter, that's enough to make sure we
        # used the right language.
        with override(language='ar'):
            expected_message = get_message(expected_response_code).msg
        # Strip off everything from the first replaceable parameter
        if '{' in expected_message:
            offset = expected_message.find('{')
            expected_message = expected_message[:offset]
        if '%s' in expected_message:
            offset = expected_message.find('%s')
            expected_message = expected_message[:offset]
        actual_message = self.get_last_response_message()
        self.assertTrue(actual_message.startswith(expected_message),
                        msg="Expected %r to start with %r" % (actual_message, expected_message))


class PollingReportTestNotWhitelisted(PollingReportLogicTestCase):
    def test_not_whitelisted(self):
        Whitelist.objects.all().delete()
        self.check_it_out("doesnt matter", NOT_WHITELISTED_NUMBER, DONT_CARE, False, False, False)

    def test_exception_during_processing(self):
        with patch.object(ReportsShortCodeHandler, 'is_addressed_to_us') as is_addressed:
            is_addressed.side_effect = ValueError
            self.check_it_out("anything", RESPONSE_SERVER_ERROR, DONT_CARE, False, False, False)


class PollingReportTestPhoneNotActivated(PollingReportLogicTestCase):
    """
    Tests for when the phone has NOT been activated to a center already.
    """
    def test_bad_message_formats(self):
        self.check_it_out("not numbers", expected_response_code=PHONE_NOT_ACTIVATED,
                          expected_msg_type=SMS.NOT_ACTIVATED,
                          expect_phone_activated=False, expect_report_saved=False,
                          expect_center_opened=False)
        self.check_it_out("27", expected_response_code=PHONE_NOT_ACTIVATED,
                          expected_msg_type=SMS.NOT_ACTIVATED,
                          expect_phone_activated=False, expect_report_saved=False,
                          expect_center_opened=False)
        self.check_it_out("27*23434*14", expected_response_code=PHONE_NOT_ACTIVATED,
                          expected_msg_type=SMS.NOT_ACTIVATED,
                          expect_phone_activated=False, expect_report_saved=False,
                          expect_center_opened=False)

    def test_outside_activation_period(self):
        self.election.delete()
        center = RegistrationCenterFactory()
        self.check_it_out("%d*%d" % (center.center_id, center.center_id),
                          POLLING_NOT_OPEN,
                          DONT_CARE,
                          expect_phone_activated=False,
                          expect_report_saved=False,
                          expect_center_opened=False,
                          # Activation period not open:
                          activation_center_opening_period=False,
                          )

    def test_mismatched_numbers(self):
        center1 = RegistrationCenterFactory()
        center2 = RegistrationCenterFactory()
        self.check_it_out("%d*%d" % (center1.center_id, center2.center_id),
                          POLLING_REPORT_CENTER_MISMATCH,
                          SMS.POLLING_REPORT_INVALID,
                          False, False,
                          expect_center_opened=False)

    def test_no_such_center(self):
        center_num = 99999
        self.check_it_out("%d*%d" % (center_num, center_num),
                          INVALID_CENTER_ID,
                          SMS.POLLING_REPORT_INVALID,
                          False, False,
                          expect_center_opened=False)

    def test_valid_activation_message(self):
        center = RegistrationCenterFactory()
        # The LAST message we receive will be that the center was opened,
        # but we'll also check that we got a PHONE_ACTIVATED before that
        self.check_it_out("%d*%d" % (center.center_id, center.center_id),
                          CENTER_OPENED,
                          SMS.ACTIVATE,
                          expect_phone_activated=True,
                          expect_report_saved=False,
                          expect_center_opened=True)
        self.assertIn(PHONE_ACTIVATED, self.get_all_response_codes())
        StaffPhone.objects.get(phone_number=self.NUMBER,
                               registration_center=center)


class CenterOpenTestPhoneActivated(PollingReportLogicTestCase):
    """Phone activated, one number in the message"""
    def setUp(self):
        super(CenterOpenTestPhoneActivated, self).setUp()
        self.center = RegistrationCenterFactory()
        # Activate the phone to the center:
        StaffPhone.objects.create(phone_number=self.NUMBER, registration_center=self.center)

    def test_valid_center_opening(self):
        # Center opening message
        self.check_it_out(
            "%d*%d" % (CENTER_OPEN_INDICATOR, self.center.center_id),
            expected_response_code=CENTER_OPENED,
            expected_msg_type=SMS.ACTIVATE,
            expect_phone_activated=DONT_CARE,  # it already was
            expect_report_saved=False,
            expect_center_opened=True
        )
        CenterOpen.objects.get(phone_number=self.NUMBER,
                               registration_center=self.center)

    def test_wrong_center_center_opening(self):
        # Center opening message, not the center the phone is activated to
        center2 = RegistrationCenterFactory()
        self.check_it_out(
            "%d*%d" % (CENTER_OPEN_INDICATOR, center2.center_id),
            expected_response_code=CENTER_OPENING_NOT_AUTHORIZED,
            expected_msg_type=SMS.NOT_ACTIVATED,
            expect_phone_activated=DONT_CARE,  # it already was
            expect_report_saved=False,
            expect_center_opened=False
        )

    def test_invalid_center_center_opening(self):
        # Center opening message, not a valid center
        self.check_it_out(
            "%d*99" % CENTER_OPEN_INDICATOR,
            expected_response_code=INVALID_CENTER_ID,
            expected_msg_type=SMS.POLLING_REPORT_INVALID,
            expect_phone_activated=DONT_CARE,  # it already was
            expect_report_saved=False,
            expect_center_opened=False
        )

    def test_not_in_center_opening_period(self):
        self.check_it_out(
            "%d*%d" % (CENTER_OPEN_INDICATOR, self.center.center_id),
            expected_response_code=POLLING_NOT_OPEN,
            expected_msg_type=DONT_CARE,
            expect_phone_activated=DONT_CARE,  # it already was
            expect_report_saved=False,
            expect_center_opened=False,
            activation_center_opening_period=False,
        )


class PollingReportTestPhoneActivated(PollingReportLogicTestCase):
    """
    Tests for when the phone HAS been activated to a center already
    and message has two numbers
    """
    def setUp(self):
        super(PollingReportTestPhoneActivated, self).setUp()
        self.center = RegistrationCenterFactory()
        # Activate the phone to the center:
        StaffPhone.objects.create(phone_number=self.NUMBER, registration_center=self.center)
        # Create some registrations so that reports don't arrive for a center with no registrations.
        create_batch(RegistrationFactory, 11, registration_center=self.center, archive_time=None)

    def test_activated_poll_report_but_polling_period_not_open(self):
        # Looks like a poll report but polling is not open
        self.check_it_out(
            "%d*2" % FIRST_PERIOD_NUMBER,
            expected_response_code=POLLING_NOT_OPEN,
            expected_msg_type=DONT_CARE,
            expect_phone_activated=DONT_CARE,  # it already was
            expect_report_saved=False,
            expect_center_opened=False,
            polling_report_period=False
        )

    def test_valid_report_period_first(self):
        # A valid polling report
        self.check_it_out(
            "%d*2" % FIRST_PERIOD_NUMBER,
            expected_response_code=POLLING_REPORT_RECEIVED,
            expected_msg_type=SMS.POLLING_REPORT,
            expect_phone_activated=DONT_CARE,  # it already was
            expect_report_saved=True,
            expect_center_opened=False
        )
        PollingReport.objects.get(registration_center=self.center,
                                  period_number=FIRST_PERIOD_NUMBER,
                                  num_voters=2)

    def test_valid_report_period_last(self):
        # A valid polling report
        self.check_it_out(
            "%d*2" % LAST_PERIOD_NUMBER,
            expected_response_code=POLLING_REPORT_RECEIVED,
            expected_msg_type=SMS.POLLING_REPORT,
            expect_phone_activated=DONT_CARE,  # it already was
            expect_report_saved=True,
            expect_center_opened=False
        )
        PollingReport.objects.get(registration_center=self.center,
                                  period_number=LAST_PERIOD_NUMBER,
                                  num_voters=2)

    def test_valid_report_copy_center(self):
        # A valid polling report to a copy center
        copy_center = RegistrationCenterFactory(copy_of=self.center)
        # Replace the StaffPhone with one registered to the copy center.
        StaffPhone.objects.all().delete()
        StaffPhone.objects.create(phone_number=self.NUMBER, registration_center=copy_center)
        self.check_it_out(
            "%d*2" % LAST_PERIOD_NUMBER,
            expected_response_code=POLLING_REPORT_RECEIVED,
            expected_msg_type=SMS.POLLING_REPORT,
            expect_phone_activated=DONT_CARE,  # it already was
            expect_report_saved=True,
            expect_center_opened=False
        )
        PollingReport.objects.get(registration_center=copy_center,
                                  period_number=LAST_PERIOD_NUMBER,
                                  num_voters=2)

    def test_valid_report_high_turnout(self):
        # A valid polling report, but with high turnout
        self.check_it_out(
            "%d*10" % LAST_PERIOD_NUMBER,
            expected_response_code=POLLING_REPORT_RECEIVED_VERY_HIGH_TURNOUT,
            expected_msg_type=SMS.POLLING_REPORT,
            expect_phone_activated=DONT_CARE,  # it already was
            expect_report_saved=True,
            expect_center_opened=False
        )
        PollingReport.objects.get(registration_center=self.center,
                                  period_number=LAST_PERIOD_NUMBER,
                                  num_voters=10)

    def test_valid_report_with_no_registrations(self):
        # A valid polling report, but to a center with 0 registrations
        Registration.objects.filter(registration_center=self.center).update(archive_time=now())
        self.check_it_out(
            "%d*10" % LAST_PERIOD_NUMBER,
            expected_response_code=POLLING_REPORT_RECEIVED_NO_REGISTRANTS,
            expected_msg_type=SMS.POLLING_REPORT,
            expect_phone_activated=DONT_CARE,  # it already was
            expect_report_saved=True,
            expect_center_opened=False
        )
        PollingReport.objects.get(registration_center=self.center,
                                  period_number=LAST_PERIOD_NUMBER,
                                  num_voters=10)

    def test_bad_first_number_of_two(self):
        # Not quite a polling report nor a center open message
        self.check_it_out(
            "%d*2" % (LAST_PERIOD_NUMBER + 1),
            expected_response_code=POLLING_REPORT_INVALID,
            expected_msg_type=SMS.POLLING_REPORT_INVALID,
            expect_phone_activated=DONT_CARE,  # it already was
            expect_report_saved=False,
            expect_center_opened=False
        )


class PrelimVoteReportTestPhoneActivated(PollingReportLogicTestCase):
    def setUp(self):
        super(PrelimVoteReportTestPhoneActivated, self).setUp()
        self.center = RegistrationCenterFactory()
        # Activate the phone to the center:
        StaffPhone.objects.create(phone_number=self.NUMBER, registration_center=self.center)
        self.election = ElectionFactory(
            polling_start_time=now() - timedelta(hours=2),
            polling_end_time=now() + timedelta(hours=2),
        )

    def test_prelim_vote_report(self):
        self.check_it_out("5#3#2",
                          expected_response_code=PRELIMINARY_VOTES_REPORT,
                          expected_msg_type=SMS.POLLING_REPORT,
                          expect_phone_activated=DONT_CARE,
                          expect_report_saved=False,
                          expect_center_opened=False,
                          expect_votes_saved=True)
        report = PreliminaryVoteCount.objects.get(
            election=self.election,
            option=3
        )
        self.assertEqual(2, report.num_votes)


class BadMessageTestPhoneActivatedNeitherOneNorTwoNumbers(PollingReportLogicTestCase):
    def setUp(self):
        super(BadMessageTestPhoneActivatedNeitherOneNorTwoNumbers, self).setUp()
        self.center = RegistrationCenterFactory()
        # Activate the phone to the center:
        StaffPhone.objects.create(phone_number=self.NUMBER, registration_center=self.center)

    def test_bad_message_formats(self):
        self.check_it_out("not numbers", expected_response_code=POLLING_REPORT_INVALID,
                          expected_msg_type=SMS.POLLING_REPORT_INVALID,
                          expect_phone_activated=DONT_CARE, expect_report_saved=False,
                          expect_center_opened=False)
        self.check_it_out("", expected_response_code=POLLING_REPORT_INVALID,
                          expected_msg_type=SMS.POLLING_REPORT_INVALID,
                          expect_phone_activated=DONT_CARE, expect_report_saved=False,
                          expect_center_opened=False)
        self.check_it_out("27*23434*14", expected_response_code=POLLING_REPORT_INVALID,
                          expected_msg_type=SMS.POLLING_REPORT_INVALID,
                          expect_phone_activated=DONT_CARE, expect_report_saved=False,
                          expect_center_opened=False)
