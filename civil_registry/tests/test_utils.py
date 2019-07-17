from django.test import TestCase
from django.utils.timezone import now

from civil_registry.tests.factories import CitizenFactory
from civil_registry.utils import get_citizen_by_national_id, is_valid_fbr_number


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


class ValidFBRNumberTest(TestCase):

    def test_integer_valid(self):
        self.assertTrue(is_valid_fbr_number(123))

    def test_string_of_digits_valid(self):
        self.assertTrue(is_valid_fbr_number('123'))

    def test_string_of_characters_then_digits_valid(self):
        self.assertTrue(is_valid_fbr_number('a123'))
        self.assertTrue(is_valid_fbr_number('foo123'))

    def test_invalid(self):
        # trailing characters invalid
        self.assertFalse(is_valid_fbr_number('foo123foo'))
        # no digits invalid
        self.assertFalse(is_valid_fbr_number('foo'))
        self.assertFalse(is_valid_fbr_number('a'))
        # nonleading characters
        self.assertFalse(is_valid_fbr_number('foo1bar2'))
        # non alphabetic characters
        self.assertFalse(is_valid_fbr_number('#123'))
        self.assertFalse(is_valid_fbr_number('#$%-'))
        # whitespace
        self.assertFalse(is_valid_fbr_number('123 456'))
