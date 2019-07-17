# -*- coding: utf-8 -*-
import datetime

from django.test import TestCase
from django.test.utils import override_settings

from pytz import timezone

from .base import LibyaTest, LibyaRapidTest
from libya_elections.constants import CENTER_ID_MAX_INT_VALUE, CENTER_ID_MIN_INT_VALUE
from register.tests.factories import RegistrationFactory
from ..utils import tool_1_enabled, remaining_registrations, center_opening_enabled, \
    phone_activation_enabled, is_center_id_valid
from voting.models import Election
from voting.tests.factories import RegistrationPeriodFactory, ElectionFactory


class RegistrationIsOpenTest(LibyaTest):
    """
    Test that tool_1_enabled() works correctly.
    """
    def test_is_open(self):
        tz = timezone('Libya')
        day_before_start_day = tz.localize(datetime.datetime(2013, 3, 14))
        second_before_start_time = tz.localize(datetime.datetime(2013, 3, 15, 7, 59, 59))
        start_time = tz.localize(datetime.datetime(2013, 3, 15, 8, 0))
        middle = tz.localize(datetime.datetime(2013, 4, 1))
        second_before_end_time = tz.localize(datetime.datetime(2013, 4, 15, 19, 59, 59))
        end_time = tz.localize(datetime.datetime(2013, 4, 15, 20, 0, 0))
        second_after_end_time = tz.localize(datetime.datetime(2013, 4, 15, 20, 0, 1))
        day_after_end_day = tz.localize(datetime.datetime(2013, 4, 16))

        RegistrationPeriodFactory(start_time=start_time, end_time=end_time)
        data = [
            (day_before_start_day, False),
            (second_before_start_time, False),
            (start_time, True),
            (middle, True),
            (second_before_end_time, True),
            (end_time, False),
            (second_after_end_time, False),
            (day_after_end_day, False),
        ]
        for time, expected_value in data:
            self.assertEqual(expected_value, tool_1_enabled(as_of=time),
                             msg="At %s, expected %s" % (time, expected_value))


class ActivationAndCenterOpeningIsOpenTest(LibyaTest):
    """
    Test that phone_activation_and_center_opening_enabled works properly.

    Activation and center opening reports are allowed from midnight 2 days before polling starts
    until the end of polling.
    """
    def test_is_open(self):
        TIMEZONE = 'Libya'

        tz = timezone(TIMEZONE)

        # Polling period
        start_time = tz.localize(datetime.datetime(2013, 3, 15, 8, 0))
        end_time = tz.localize(datetime.datetime(2013, 4, 15, 20, 0, 0))

        # Delete any pre-existing elections
        Election.objects.all().delete()

        ElectionFactory(
            polling_start_time=start_time,
            polling_end_time=end_time,
        )

        with override_settings(TIME_ZONE=TIMEZONE):
            data = [
                (tz.localize(datetime.datetime(2013, 3, 12, 23, 59)), False),
                (tz.localize(datetime.datetime(2013, 3, 13, 0, 0)), True),
                (tz.localize(datetime.datetime(2013, 3, 13, 8, 0)), True),
                (tz.localize(datetime.datetime(2013, 3, 14, 8, 0)), True),
                (tz.localize(datetime.datetime(2013, 3, 15, 0, 0)), True),
                (tz.localize(datetime.datetime(2013, 3, 15, 8, 0)), True),
                # Periods do not include their end time
                (tz.localize(datetime.datetime(2013, 4, 15, 19, 59, 59)), True),
                (tz.localize(datetime.datetime(2013, 4, 15, 20, 0, 0)), False)

            ]
            for time, expected_value in data:
                self.assertEqual(expected_value,
                                 phone_activation_enabled(as_of=time),
                                 msg="With polling start at %s and end at %s, expected "
                                     "phone_activation_enabled "
                                     "to be %s at %s but it was not" %
                                     (start_time, end_time,
                                      expected_value, time))
                self.assertEqual(expected_value,
                                 center_opening_enabled(as_of=time),
                                 msg="With polling start at %s and end at %s, expected "
                                     "center_opening_enabled "
                                     "to be %s at %s but it was not" %
                                     (start_time, end_time,
                                      expected_value, time))


class ThwartEmojiTest(LibyaRapidTest):
    """
    Test that parens get surrounded by spaces to prevent phones from autocorrecting to emoji.
    """

    def test_that_we_surround_parens_with_spaces(self):
        self.send('(8)', self.create_connection())
        # We don't use `self.get_last_response_message`, because that will get us
        # msg.raw_text, and we specifically want to see the postprocessed msg that
        # we would send to the phone, which is stored in msg.text
        self.assertEqual(self.get_last_response().text, '( 8 )')

    def test_result_unchanged_if_no_transformations_match(self):
        raw_text = '()'
        self.send(raw_text, self.create_connection())
        self.assertEqual(self.get_last_response().text, raw_text)


class RemainingRegistrationsTest(TestCase):
    @override_settings(MAX_REGISTRATIONS_PER_PHONE=2)
    def test_remaining_registrations(self):
        PHONE_NUMBER = '123987'
        self.assertEqual(2, remaining_registrations(PHONE_NUMBER))
        RegistrationFactory(archive_time=None, sms__from_number=PHONE_NUMBER)
        self.assertEqual(1, remaining_registrations(PHONE_NUMBER))
        RegistrationFactory(archive_time=None, sms__from_number=PHONE_NUMBER)
        self.assertEqual(0, remaining_registrations(PHONE_NUMBER))
        # Less than zero remaining, should still return 0
        RegistrationFactory(archive_time=None, sms__from_number=PHONE_NUMBER)
        self.assertEqual(0, remaining_registrations(PHONE_NUMBER))


class MiscellaneousUtilityTest(TestCase):

    def test_is_center_id_valid(self):
        self.assertFalse(is_center_id_valid(None))
        self.assertFalse(is_center_id_valid(''))
        self.assertFalse(is_center_id_valid('abc'))
        self.assertFalse(is_center_id_valid(CENTER_ID_MAX_INT_VALUE + 1))
        self.assertTrue(is_center_id_valid(CENTER_ID_MIN_INT_VALUE))
        self.assertTrue(is_center_id_valid(CENTER_ID_MAX_INT_VALUE))
