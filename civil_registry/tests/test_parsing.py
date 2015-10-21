# coding: utf-8
from __future__ import unicode_literals
from datetime import date

from django.test import TestCase

from civil_registry.parsing import strip_space_and_quotes, match_line_re, match_line_split, break_line, FIELD_NAMES, \
    line_to_dictionary, get_records

# INSERT INTO T_PERSONAL_DATA(PERSON_ID,NAME,FATHER_NAME_AR,GRAND_FATHER_NAME_AR,FAM_NAME,
# MOTHER_NAME_AR,GENDER,DATE_OF_BIRTH,ADDRESS,NATIONAL_ID,REGISTRY_NO,OFFICE_ID,BRANCH_ID,STATE)

ARABIC_NAME_WITH_COMMAS = "ملائك, ة نائلة"
valid_input_with_commas = (
    #         personid  name           father    GF          family      mother
    """VALUES(2566665, '%s', 'جمعة', 'عبدالصمد', 'عبدالرحمن', 'صفية علي', """
    """1, '7/9/1969', 'الاسكندرية','119690261935', '1009332066', 35, 54, 0);\r\n"""
    % ARABIC_NAME_WITH_COMMAS)

result_with_commas = {
    'civil_registry_id': 2566665,
    'first_name': ARABIC_NAME_WITH_COMMAS,
    'father_name': 'جمعة',
    'grandfather_name': 'عبدالصمد',
    'family_name': 'عبدالرحمن',
    'mother_name': 'صفية علي',
    'gender': 1,
    'birth_date': date(1969, 9, 7),
    'address': 'الاسكندرية',
    'national_id': 119690261935,
    'fbr_number': 1009332066,
    'office_id': 35,
    'branch_id': 54,
    'state': 0,
}

ARABIC_NAME = "ملائك ة نائلة"
valid_input = (
    """VALUES(2566665, '%s', 'جمعة', 'عبدالصمد', 'عبدالرحمن', 'صفية علي', """
    """1, '7/9/1969', 'الاسكندرية','119690261935', '1009332066', 35, 54, 0);\r\n"""
    % ARABIC_NAME)


class LineToDictionaryTest(TestCase):
    def test_line_with_commas(self):
        result = line_to_dictionary(valid_input_with_commas)
        self.assertEqual(len(FIELD_NAMES), len(result))
        self.maxDiff = None
        self.assertEqual(result_with_commas, result)

    def test_invalid_input(self):
        # Validates input using a form; make sure it catches problems
        invalid_input = valid_input.replace('7/9/1969', '17/99/2309')
        with self.assertRaises(ValueError):
            line_to_dictionary(invalid_input)


class StripSpaceAndQuotesTest(TestCase):
    """Test strip_space_and_quotes() method"""
    def test_strip_space_and_quotes(self):
        # It strips spaces and single quotes
        self.assertEqual('xyz', strip_space_and_quotes(" xyz "))
        self.assertEqual('xyz', strip_space_and_quotes(" 'xyz' "))
        self.assertEqual('xyz', strip_space_and_quotes("'xyz '"))


class MatchLineReTest(TestCase):
    """match_line_re splits a VALUES line into its string parts and strips
    leading and trailing spaces and single quotes, returning a tuple of strings.
    It should work even if values have commas in them
    """

    def test_match_line_re(self):
        result = match_line_re(valid_input_with_commas)
        self.assertEqual(14, len(result))
        (civil_registry_id, national_id, fbr_number,
         first_name, father_name,
         grandfather_name, mother_name,
         family_name, gender, birth_date,
         address, office_id, branch_id, state) = result
        self.assertEqual(
            ('2566665', '119690261935', '1009332066',
             ARABIC_NAME_WITH_COMMAS, 'جمعة',
             'عبدالصمد', 'صفية علي',
             'عبدالرحمن', '1', '7/9/1969',
             'الاسكندرية', '35', '54', '0'),
            (civil_registry_id, national_id, fbr_number,
             first_name, father_name,
             grandfather_name, mother_name,
             family_name, gender, birth_date,
             address, office_id, branch_id, state)
        )

    def test_match_line_re_invalid_line(self):
        invalid_input = valid_input[0]
        invalid_input = invalid_input.replace(');\r\n', ',0,2);\r\n')
        with self.assertRaises(ValueError):
            match_line_re(invalid_input)


class MatchLineSplitTest(TestCase):
    """match_line_split splits a VALUES line into its string parts and strips
    leading and trailing spaces and single quotes, returning a tuple of strings"""

    def test_match_line_split(self):
        result = match_line_split(valid_input)
        self.assertEqual(14, len(result))
        (civil_registry_id, national_id, fbr_number,
         first_name, father_name,
         grandfather_name, mother_name,
         family_name, gender, birth_date,
         address, office_id, branch_id, state) = result
        self.assertEqual('2566665', civil_registry_id)
        self.assertEqual(ARABIC_NAME, first_name)
        self.assertEqual('7/9/1969', birth_date)
        self.assertEqual('35', office_id)
        self.assertEqual('0', state)


class BreakLineTest(TestCase):
    def test_line_with_commas(self):
        result = break_line(valid_input_with_commas)
        self.assertEqual(len(FIELD_NAMES), len(result))

    def test_line_without_commas(self):
        result = break_line(valid_input)
        self.assertEqual(len(FIELD_NAMES), len(result))


def mock_line_to_dictionary(input):
    # Just return whatever we're given
    return input


class GetRecordsTest(TestCase):
    def setUp(self):
        # Just use a list of strings as the input file, it's still an iterator
        self.input = ["VALUES(%d" % i for i in range(10)]

    def test_plain(self):
        # If we dummy up the parser, we get back our input
        output = list(get_records(self.input, line_parser=mock_line_to_dictionary))
        self.assertEqual(self.input, output)

    def test_ignore_non_VALUES_lines(self):
        input = ['VALUES(1', 'other', 'VALUES(2']
        output = list(get_records(input, line_parser=mock_line_to_dictionary))
        self.assertEqual([input[0], input[2]], output)
