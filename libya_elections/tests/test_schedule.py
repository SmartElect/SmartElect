import datetime

from django.test import TestCase
from libya_elections.utils import at_noon


class ScheduleTest(TestCase):
    def test_at_noon(self):
        # at_noon returns a datetime with the right values
        dt = datetime.datetime(1970, 2, 3, 4, 5, 6, 7)
        result = at_noon(dt)
        self.assertEqual(12, result.hour)
        self.assertEqual(0, result.minute)
        self.assertEqual(0, result.second)
        self.assertEqual(0, result.microsecond)
