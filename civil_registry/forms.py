from django import forms
from django.core.exceptions import ValidationError
from django.utils.timezone import now

from civil_registry.models import AbstractCitizen
from libya_elections.constants import LIBYA_DATE_FORMAT


class CitizenRecordForm(forms.ModelForm):
    birth_date = forms.DateField(
        input_formats=[LIBYA_DATE_FORMAT],
    )

    class Meta:
        fields = [
            'civil_registry_id',
            'national_id',
            'fbr_number',
            'first_name',
            'father_name',
            'grandfather_name',
            'family_name',
            'mother_name',
            'birth_date',
            'gender',
            'address',
            'office_id',
            'branch_id',
            'state'
        ]
        model = AbstractCitizen

    def clean_birth_date(self):
        if self.cleaned_data['birth_date'] > now().date():
            raise ValidationError("Citizen hasn't been born yet")
        return self.cleaned_data['birth_date']

    def clean(self):
        # A bit more validation
        # The first digit of the national ID should match
        # the gender
        first_digit = int(str(self.cleaned_data['national_id'])[0])
        gender = self.cleaned_data['gender']
        if first_digit != gender:
            raise ValidationError("First digit of national ID does not match gender")
        return self.cleaned_data
