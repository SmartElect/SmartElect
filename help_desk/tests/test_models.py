import datetime

from django.test import TestCase
from django.utils.timezone import now

from register.tests.factories import RegistrationFactory

from help_desk.models import Case


class CaseModelTest(TestCase):
    def test_registration_unlocked(self):
        reg = RegistrationFactory()
        case = Case()
        self.assertFalse(case.registration_unlocked())
        case.registration = reg
        self.assertFalse(case.registration_unlocked())
        reg.unlocked_until = now() + datetime.timedelta(hours=1)
        self.assertTrue(case.registration_unlocked())
        case.relock_registration()
        self.assertFalse(case.registration_unlocked())
        case.registration = None
        self.assertFalse(case.registration_unlocked())
