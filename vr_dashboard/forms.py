from django import forms
from django.utils.translation import ugettext_lazy as _

from libya_elections.constants import CENTER_ID_MAX_INT_VALUE, CENTER_ID_MIN_INT_VALUE
from libya_elections.phone_numbers import PhoneNumberFormField
from register.models import RegistrationCenter


def get_invalid_center_error_string(center_id):
    """ Assumptions: This will be escaped before presenting to the user
    in case user input is provided directly.
    """
    return _("Center %s is not a valid center.") % center_id


class PhoneAndMessageQueryForm(forms.Form):
    phone_number = PhoneNumberFormField(required=False, disable_help_text=True)
    center_id = forms.IntegerField(min_value=CENTER_ID_MIN_INT_VALUE,
                                   max_value=CENTER_ID_MAX_INT_VALUE,
                                   required=False,
                                   widget=forms.TextInput)

    search_usage_message = _('Either a phone number or a center must be supplied, but not both.')

    def clean(self):
        cleaned_data = super(PhoneAndMessageQueryForm, self).clean()
        phone_number = cleaned_data.get('phone_number')
        center_id = cleaned_data.get('center_id')
        if not phone_number and not center_id:
            raise forms.ValidationError(self.search_usage_message)
        if phone_number and center_id:
            raise forms.ValidationError(self.search_usage_message)

    def clean_center_id(self):
        center_id = self.cleaned_data.get('center_id')
        if center_id and not RegistrationCenter.objects.filter(center_id=center_id).exists():
            raise forms.ValidationError(get_invalid_center_error_string(center_id))
        return center_id
