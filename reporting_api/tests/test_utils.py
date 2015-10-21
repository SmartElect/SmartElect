# Python imports
import datetime

# 3rd party imports
from django.test import TestCase
from django.utils.timezone import now

# Project imports
from register.tests.test_models import RegistrationCenterFactory
from register.utils import registration_in_progress
from reporting_api.data_pull_common import get_active_registration_locations, \
    get_all_polling_locations
from reporting_api.reports import calc_yesterday, parse_iso_datetime, printable_iso_datetime
from reporting_api.utils import get_datetime_from_local_date_and_time
from voting.tests.factories import RegistrationPeriodFactory


class TestReportUtils(TestCase):

    def test_yesterday_no_dates(self):
        string_and_date = calc_yesterday(())
        self.assertEqual(string_and_date, (None, None))

    def test_yesterday_from_single_date(self):
        today = now()
        today_str = today.strftime('%Y-%m-%d')
        date_and_string = calc_yesterday([today_str])
        # since there's just one date provided, yesterday can only
        # be that date regardless of other factors
        self.assertEqual(date_and_string, (today.date(), today_str))
        # try again, providing the date object
        date_and_string = calc_yesterday([today_str], [today.date()])
        self.assertEqual(date_and_string, (today.date(), today_str))

    def test_yesterday_general(self):
        today = now()
        first_dt = today - datetime.timedelta(7)
        input_strings = [(first_dt + datetime.timedelta(delta_days)).strftime('%Y-%m-%d')
                         for delta_days in range(7)]

        # the behavior depends on the current datetime relative to registration end,
        # so try it with registration end before and after the current time
        reg_period = RegistrationPeriodFactory(start_time=today - datetime.timedelta(days=5),
                                               end_time=today)
        for fake_registration_end in [today - datetime.timedelta(days=1),
                                      today + datetime.timedelta(days=1)]:
            reg_period.end_time = fake_registration_end
            reg_period.save()
            if registration_in_progress(as_of=today.date()):
                expected_str = input_strings[-2]
            else:
                expected_str = input_strings[-1]
            expected_date = datetime.datetime.strptime(expected_str, '%Y-%m-%d').date()
            date_and_string = calc_yesterday(input_strings)
            self.assertEqual(date_and_string, (expected_date, expected_str))
            # try again, providing the date objects
            input_dates = [datetime.datetime.strptime(s, '%Y-%m-%d').date()
                           for s in input_strings]
            date_and_string = calc_yesterday(input_strings, input_dates)
            self.assertEqual(date_and_string, (expected_date, expected_str))

    def test_iso_parsing(self):
        times = (
            '2015-02-20T10:09:32.123456+02:00',
            '2015-02-20T10:09:32.123456',
            '2015-02-20T10:09:32+02:00',
            '2015-02-20T10:09:32')
        for s in times:
            dt = parse_iso_datetime(s)
            self.assertEqual((dt.year, dt.month, dt.day), (2015, 2, 20))
            self.assertEqual((dt.hour, dt.minute, dt.second), (10, 9, 32))
            self.assertEqual(dt.microsecond, 123456 if '.' in s else 0)
            if '+' in s:
                tz = dt.tzinfo
                self.assertEqual(tz.utcoffset(dt), datetime.timedelta(seconds=7200))
            else:
                self.assertEqual(dt.tzinfo, None)
            self.assertEqual(printable_iso_datetime(s), '20/02 10:09')

    def test_datetime_from_local_date_and_time(self):
        times = (
            ('2015-02-20', '10:09:32.123456'),
            ('2015-02-20', '10:09:32'),
        )
        for d, t in times:
            dt = get_datetime_from_local_date_and_time(d, t)
            self.assertEqual(dt.strftime('%Y-%m-%d'), d)
            time_fmt = '%H:%M:%S.%f' if dt.microsecond else '%H:%M:%S'
            self.assertEqual(dt.strftime(time_fmt), t)

    def test_registration_center_queries(self):
        rc1 = RegistrationCenterFactory(reg_open=True)
        rc2 = RegistrationCenterFactory(reg_open=False)

        for_registration = get_active_registration_locations()
        all_locations = get_all_polling_locations()

        self.assertEquals(sorted(for_registration.keys()), sorted([rc1.center_id]))
        self.assertEquals(sorted(all_locations.keys()), sorted([rc1.center_id, rc2.center_id]))
