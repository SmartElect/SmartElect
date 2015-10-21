from datetime import timedelta
from django.forms import model_to_dict
from django.test import TestCase
from django.utils.timezone import now
from civil_registry.forms import CitizenRecordForm
from civil_registry.tests.factories import CitizenFactory
from libya_elections.constants import FEMALE


def stringize(data):
    """Given data for a citizen where integers are really integers
    and such, make them all into strings."""

    for field in data.keys():
        if field == 'birth_date':
            data[field] = data[field].strftime("%d/%m/%Y")
            # strftime always zero-pads, the dump doesn't, so get rid of
            # those zeros
            data[field] = '/'.join([str(int(f)) for f in data[field].split('/')])
        else:
            data[field] = str(data[field])
    return data


class CitizenRecordFormTest(TestCase):
    def test_simple(self):
        citizen = CitizenFactory()
        data = model_to_dict(citizen)
        data = stringize(data)
        form = CitizenRecordForm(data)
        self.assertTrue(form.is_valid(), msg="Form errors: %r" % form.errors)

    def test_not_born_yet(self):
        tomorrow = (now() + timedelta(hours=24)).date()
        citizen = CitizenFactory(birth_date=tomorrow)
        data = model_to_dict(citizen)
        data = stringize(data)
        form = CitizenRecordForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn('birth_date', form.errors)

    def test_wrong_gender_for_national_id(self):
        citizen = CitizenFactory(
            gender=FEMALE,
            national_id=123456789012,  # expecting male gender
        )
        data = model_to_dict(citizen)
        data = stringize(data)
        form = CitizenRecordForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn("does not match gender", str(form.errors))
