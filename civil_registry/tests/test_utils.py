from django.test import TestCase
from django.utils.timezone import now

from civil_registry.tests.factories import CitizenFactory
from civil_registry.utils import get_citizen_by_national_id


class GetCitizenByNIDTest(TestCase):
    def test_basic_get(self):
        citizen = CitizenFactory()
        citizen2 = get_citizen_by_national_id(citizen.national_id)
        self.assertEqual(citizen.pk, citizen2.pk)

    def test_no_such_citizen(self):
        citizen = get_citizen_by_national_id(99)
        self.assertIsNone(citizen)

    def test_missing_citizen(self):
        citizen = CitizenFactory(missing=now())
        citizen2 = get_citizen_by_national_id(citizen.national_id)
        self.assertIsNone(citizen2)
