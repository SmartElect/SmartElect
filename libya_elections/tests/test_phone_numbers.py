from datetime import datetime
import re
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rapidsms.models import Connection, Backend
from libya_elections.phone_numbers import format_phone_number, canonicalize_phone_number, \
    PhoneNumberField, PhoneNumberFormField, get_random_phone_number, \
    best_connection_for_phone_number
from libya_elections.utils import get_random_number_string


class TestFormatting(TestCase):
    def test_format_phone_number(self):
        self.assertEqual(format_phone_number('218923456789'), '+218 (0)92-345-6789')
        self.assertEqual(format_phone_number('8821612340058'), '+88216-12340058')
        self.assertEqual(format_phone_number('882161234005'), '+88216-1234005')

    def test_canonicalize_phone_number(self):
        test_data = [
            ('+218 (0)91-345-6789', '218913456789'),
            ('+218 91-345-6789', '218913456789'),
            ('0923456789', '218923456789'),
            ('0987654321', '218987654321'),
            ('+88216-12340058', '8821612340058'),
            ('+88216-1234005', '882161234005'),
        ]
        for input, expected_result in test_data:
            actual_result = canonicalize_phone_number(input)
            self.assertEqual(expected_result, actual_result,
                             msg="%s was formatted as %s but should have been %s" %
                                 (input, actual_result, expected_result))


class PhoneNumberModelFieldTest(TestCase):
    """
    We test field validation the way Django does: by calling the field's clean() method,
    using None as the model instance.

    Example:
      https://github.com/django/django/blob/fdc936c9130cf4fb5d59869674b9a31cc79a7999/tests/model_fields/test_charfield.py#L38
    """

    # relax the regex so that we're testing the max_length
    @override_settings(PHONE_NUMBER_REGEX='.*')
    def test_max_length(self):
        # Test validation of phone number length
        # Create the field inside the context where we've overridden the regex
        phone_number_field = PhoneNumberField()
        exact_length_number = get_random_number_string(settings.MAX_PHONE_NUMBER_LENGTH)
        self.assertEqual(phone_number_field.clean(exact_length_number, None),
                         exact_length_number)

        too_long = get_random_number_string(1 + settings.MAX_PHONE_NUMBER_LENGTH)
        with self.assertRaises(ValidationError):
            phone_number_field.clean(too_long, None)

    @override_settings(PHONE_NUMBER_REGEX='^fred$')
    def test_regex_validation(self):
        # Test validation by the phone number regex in settings
        # Create the field inside the context where we've overridden the regex
        phone_number_field = PhoneNumberField()
        with self.assertRaises(ValidationError):
            phone_number_field.clean('joe', None)
        self.assertEqual(phone_number_field.clean('fred', None), 'fred')

    def test_current_number_formats(self):
        # Test the number formats we're currently using in settings
        # The formats of phone numbers currently valid in Libya:
        #   218 + 9 digits  (Libyana, Al Madar)
        #   88216 + 8 digits  (Thuraya)
        phone_number_field = PhoneNumberField()
        test_data = [
            # ('test number', whether should be valid)
            ('218923456789', True),
            ('217123456789', False),
            ('0218923456789', False),
            ('21892345678', False),
            ('218-923456789', False),
            ('218923456789 x123', False),

            ('8821612345678', True),
            ('8821512345678', False),
            ('88216-12345678', False),
            ('882161234567', False),
            ('88216123456789', False),
            ('08821612345678', False),

            ('19199510052', False),
            ('9199510052', False),
            ('(919) 951-0052', False),
        ]
        for input, should_be_valid in test_data:
            if should_be_valid:
                self.assertEqual(phone_number_field.clean(input, None), input)
            else:
                with self.assertRaises(ValidationError):
                    phone_number_field.clean(input, None)


class PhoneNumberFormFieldTest(TestCase):
    # relax the regex so that we're testing the max_length
    @override_settings(PHONE_NUMBER_REGEX='.*')
    def test_max_length(self):
        # Test validation of phone number length
        # Create the form inside the context where we've overridden the regex
        class TestForm(forms.Form):
            phone_number = PhoneNumberFormField()
        exact_length_number = get_random_number_string(settings.MAX_PHONE_NUMBER_LENGTH)
        too_long = get_random_number_string(1 + settings.MAX_PHONE_NUMBER_LENGTH)
        self.assertTrue(TestForm(data=dict(phone_number=exact_length_number)).is_valid())
        self.assertFalse(TestForm(data=dict(phone_number=too_long)).is_valid(),
                         msg="%s should have been too long" % too_long)

    def test_current_number_formats(self):
        # Test the number formats we're currently using in settings
        # The formats of phone numbers currently valid in Libya:
        #   218 + 9 digits  (Libyana, Al Madar)
        #   88216 + 8 digits  (Thuraya)
        class TestForm(forms.Form):
            phone_number = PhoneNumberFormField()
        test_data = [
            # ('test number', whether should be valid)
            ('218923456789', True),
            ('217123456789', False),
            ('0218923456789', False),
            ('21892345678', False),
            ('218-923456789', True),
            ('218923456789 x123', False),

            ('8821612345678', True),
            ('8821512345678', False),
            ('88216-12345678', True),
            ('882161234567', False),
            ('88216123456789', False),
            ('08821612345678', False),

            ('19199510052', False),
            ('9199510052', False),
            ('(919) 951-0052', False),
        ]
        for input, should_be_valid in test_data:
            form = TestForm(data=dict(phone_number=input))
            if should_be_valid:
                self.assertTrue(form.is_valid(),
                                msg="Form should have been valid with phone number %s but had "
                                    "these errors: %s" % (input, form.errors))
            else:
                self.assertFalse(form.is_valid(),
                                 msg="Form should NOT have been valid with phone number %s" % input)


class BestConnectionTest(TestCase):
    def setUp(self):
        self.number = get_random_phone_number()

    def test_freshest_connection(self):
        # If there are connection objects, use most recent
        backend1 = Backend.objects.create(name="backend1")
        backend2 = Backend.objects.create(name="backend2")
        Connection.objects.create(
            identity=self.number,
            backend=backend1,
            modified_on=datetime(2014, 3, 4, 12, 9)
        )
        conn2 = Connection.objects.create(
            identity=self.number,
            backend=backend2,
            modified_on=datetime(2014, 3, 4, 12, 10)
        )
        self.assertEqual(conn2, best_connection_for_phone_number(self.number))

    @override_settings(INSTALLED_BACKENDS={
        'backend1': {
            'number_regex': re.compile(r'^1\d+$'),
        },
        'backend2': {
            'number_regex': re.compile(r'^2\d+$'),
        },
    })
    def test_matching_number(self):
        self.assertEqual('backend1', best_connection_for_phone_number('1234').backend.name)
        self.assertEqual('backend2', best_connection_for_phone_number('2345').backend.name)
        # Doesn't blow up for some other number
        best_connection_for_phone_number('3456')

    @override_settings(INSTALLED_BACKENDS={})
    def test_use_one_at_random(self):
        Backend.objects.create(name="backend1")
        Backend.objects.create(name="backend2")
        conn = best_connection_for_phone_number('1234', ["backend1"])
        self.assertEqual("backend1", conn.backend.name)
        conn = best_connection_for_phone_number('2345', ["backend2"])
        self.assertEqual("backend2", conn.backend.name)
