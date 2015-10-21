# Python imports
import datetime

# 3rd party imports
from django.test import TestCase
from django.utils.timezone import now

from vr_dashboard.views.views import last_seven_dates, parse_phone_number_fields


class TestVrDashboardUtils(TestCase):

    def test_last_seven(self):
        today = now()
        for number_of_dates in [3, 7, 10]:  # truncated week + un-truncated weeks
            first_dt = today - datetime.timedelta(number_of_dates - 1)
            input_strings = [(first_dt + datetime.timedelta(delta_days)).strftime('%Y-%m-%d')
                             for delta_days in range(number_of_dates)]
            max_result_size = number_of_dates if number_of_dates < 7 else 7
            # one case is when the last date is today
            results = last_seven_dates(input_strings)
            self.assertEquals(results, input_strings[:-1][-max_result_size:])

            # another case is when the last date is before today
            results = last_seven_dates(input_strings[:-1])
            self.assertEquals(results, input_strings[:-1][-max_result_size:])

    def test_parse_phone_number_fields(self):
        whitelisted = '8821612340058 W 2014-12-03 10:10:51+00'
        not_whitelisted = '8821612340058 X 2014-12-03 10:10:51+00'

        fields = parse_phone_number_fields(whitelisted)
        self.assertEqual(fields['number'], '+88216-12340058')
        self.assertEqual(fields['flag'], '')
        self.assertEqual(fields['error'], '')
        self.assertEqual(fields['timestamp'], '12/03 10:10')

        fields = parse_phone_number_fields(not_whitelisted)
        self.assertEqual(fields['number'], '+88216-12340058')
        self.assertEqual(fields['flag'], 'X')
        self.assertEqual(fields['error'], 'Not Whitelisted')
        self.assertEqual(fields['timestamp'], '')
