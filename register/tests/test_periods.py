import datetime

from django.test.utils import override_settings
from django.utils.timezone import now

from voting.tests.factories import RegistrationPeriodFactory, ElectionFactory

from ..tests.base import LibyaTest, PAST_DAY, FUTURE_DAY
from ..utils import tool_1_enabled, polling_reports_enabled


FIFTEEN_HOURS_AGO = now() - datetime.timedelta(hours=15)


@override_settings(ENABLE_ALL_TOOLS=False)
class PeriodsTest(LibyaTest):
    """
    Match requirements in Phases google spreadsheet:
    https://docs.google.com/a/caktusgroup.com/spreadsheet/ccc?
    key=0ApHYnffwYN6edDJSVmZaeXBqWDZnVk9ReTh6RWEyRWc&usp=drive_web#gid=0
    """

    def setUp(self):
        # Default to polling in progress
        self.election = ElectionFactory(polling_start_time=PAST_DAY, polling_end_time=FUTURE_DAY)

    def test_before_registration_opens_period(self):
        self.election.polling_start_time = FUTURE_DAY
        self.election.save()
        RegistrationPeriodFactory(start_time=FUTURE_DAY, end_time=FUTURE_DAY)
        self.assertFalse(tool_1_enabled())
        self.assertFalse(polling_reports_enabled())

    def test_during_registration(self):
        self.election.polling_start_time = FUTURE_DAY
        self.election.save()
        RegistrationPeriodFactory(start_time=PAST_DAY, end_time=FUTURE_DAY)
        self.assertTrue(tool_1_enabled())
        self.assertFalse(polling_reports_enabled())

    def test_after_registration_before_polling(self):
        self.election.polling_start_time = FUTURE_DAY
        self.election.save()
        RegistrationPeriodFactory(start_time=PAST_DAY, end_time=PAST_DAY)
        self.assertFalse(tool_1_enabled())
        self.assertFalse(polling_reports_enabled())

    def test_polling_period(self):
        RegistrationPeriodFactory(start_time=PAST_DAY, end_time=PAST_DAY)
        self.assertFalse(tool_1_enabled())
        self.assertTrue(polling_reports_enabled())

    def test_post_polling_reporting_period(self):
        self.election.polling_end_time = FIFTEEN_HOURS_AGO
        self.election.save()
        RegistrationPeriodFactory(start_time=PAST_DAY, end_time=PAST_DAY)
        self.assertFalse(tool_1_enabled())
        self.assertTrue(polling_reports_enabled())

    def test_counting_period(self):
        self.election.polling_end_time = PAST_DAY
        self.election.save()
        RegistrationPeriodFactory(start_time=PAST_DAY, end_time=PAST_DAY)
        self.assertFalse(tool_1_enabled())
        self.assertFalse(polling_reports_enabled())

    def test_reopened_reg_period(self):
        self.election.polling_end_time = PAST_DAY
        self.election.save()
        RegistrationPeriodFactory(start_time=PAST_DAY, end_time=PAST_DAY)
        self.assertFalse(tool_1_enabled())
        self.assertFalse(polling_reports_enabled())

    def test_after_reopened_reg_period(self):
        self.election.polling_end_time = PAST_DAY
        self.election.save()
        RegistrationPeriodFactory(start_time=PAST_DAY, end_time=PAST_DAY)
        self.assertFalse(tool_1_enabled())
        self.assertFalse(polling_reports_enabled())
