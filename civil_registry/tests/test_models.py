import datetime

from django.test import TestCase

from civil_registry.models import Citizen
from civil_registry.tests.factories import CitizenFactory
from register.tests.factories import RegistrationFactory


class CitizenTest(TestCase):
    def test_name_format(self):
        # We format names as First name, father name, etc.
        citizen = Citizen(first_name="FIRST",
                          father_name="FATHER",
                          grandfather_name="GRANDFATHER",
                          family_name="FAMILY",
                          mother_name="MOTHER")
        name = str(citizen)
        self.assertEqual("FIRST FATHER GRANDFATHER FAMILY", name)

    def test_is_eligible_way_too_young(self):
        TODAY = datetime.datetime(2000, 1, 1)
        citizen = Citizen(birth_date=datetime.date(1990, 1, 1))
        self.assertFalse(citizen.is_eligible(as_of=TODAY))

    def test_is_eligible_plenty_old(self):
        TODAY = datetime.datetime(2000, 1, 1)
        citizen = Citizen(birth_date=datetime.date(1970, 1, 1))
        self.assertTrue(citizen.is_eligible(as_of=TODAY))

    def test_is_eligible_today(self):
        # 18th birthday "today"
        TODAY = datetime.datetime(2000, 6, 1)
        citizen = Citizen(birth_date=datetime.date(1982, 6, 1))
        self.assertTrue(citizen.is_eligible(as_of=TODAY))

    def test_is_eligible_yesterday(self):
        # Became eligible yesterday
        TODAY = datetime.datetime(2000, 6, 2)
        citizen = Citizen(birth_date=datetime.date(1982, 6, 1))
        self.assertTrue(citizen.is_eligible(as_of=TODAY))

    def test_is_eligible_tomorrow(self):
        # Will be eligible tomorrow
        TODAY = datetime.datetime(2000, 6, 1)
        citizen = Citizen(birth_date=datetime.date(1982, 6, 2))
        self.assertFalse(citizen.is_eligible(as_of=TODAY))

    def test_is_eligible_blocked(self):
        # Blocked citizen is not eligible
        TODAY = datetime.datetime(2000, 6, 2)
        citizen = CitizenFactory(birth_date=datetime.date(1982, 6, 1))
        self.assertTrue(citizen.is_eligible(as_of=TODAY))
        citizen.block()
        citizen.save()
        self.assertFalse(citizen.is_eligible(as_of=TODAY))

    def test_block_citizen(self):
        citizen = CitizenFactory()
        RegistrationFactory(citizen=citizen, archive_time=None)
        self.assertIsNotNone(citizen.registration)
        citizen.block()
        self.assertIsNone(citizen.registration)
