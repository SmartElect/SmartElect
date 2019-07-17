# -*- coding: utf-8 -*-

from django.test import TestCase
from django.test.utils import override_settings
from django.utils.formats import date_format
from datetime import datetime, date


@override_settings(LANGUAGE_CODE='ar')
class TestCheckRegistrationPageView(TestCase):

    def test_datetime_formats(self):
        """Check Libyan datetime formats"""
        dt = datetime(2015, 10, 25, 13, 44, 00)
        self.assertEqual(date_format(dt, "SHORT_DATETIME_FORMAT"), "13:44 2015/10/25")
        self.assertEqual(date_format(dt, "DATETIME_FORMAT"), "13:44 2015/10/25")
        self.assertEqual(date_format(dt, "TIME_FORMAT"), "13:44")

    def test_date_formats(self):
        """Check Libyan date formats"""
        dt = date(2015, 10, 25)
        self.assertEqual(date_format(dt, "SHORT_DATE_FORMAT"), "2015/10/25")
        self.assertEqual(date_format(dt, "DATE_FORMAT"), "2015/10/25")
        self.assertEqual(date_format(dt, "YEAR_MONTH_FORMAT"), "2015/10")
        self.assertEqual(date_format(dt, "MONTH_DAY_FORMAT"), "10/25")
