from django.core.exceptions import ValidationError
from django.test import TestCase
from polling_reports.models import StaffPhone
from polling_reports.tests.factories import CenterOpenFactory, StaffPhoneFactory
from libya_elections.phone_numbers import get_random_phone_number

from register.tests.factories import RegistrationCenterFactory


class CenterOpenTest(TestCase):
    def test_centeropen_unicode(self):
        str(CenterOpenFactory())

    def test_staffphone_unicode(self):
        str(StaffPhoneFactory())


class TestStaffPhone(TestCase):
    def test_numbers_unique(self):
        number1 = get_random_phone_number()
        number2 = str(1 + int(number1))
        reg = RegistrationCenterFactory()
        StaffPhone.objects.create(phone_number=number1, registration_center=reg)
        StaffPhone.objects.create(phone_number=number2, registration_center=reg)
        obj = StaffPhone(phone_number=number2, registration_center=reg)
        with self.assertRaises(ValidationError):
            obj.clean()

    def test_center_may_be_soft_deleted(self):
        """Unicode method of StaffPhone associated with deleted center should not fail."""
        rc = RegistrationCenterFactory(deleted=True)
        phone = StaffPhoneFactory(registration_center=rc)
        # re-fetch the StaffPhone
        fetched_phone = StaffPhone.objects.get(id=phone.id)
        self.assertTrue(str(fetched_phone))
