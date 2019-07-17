import logging

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from captcha.fields import CaptchaField
from civil_registry.utils import get_citizen_by_national_id
from libya_elections import constants
from libya_elections.constants import MIN_NATIONAL_ID, MAX_NATIONAL_ID
from text_messages.utils import get_message

from .utils import create_arabic_trans_table

CONVERT_TO_WESTERN_DIGITS = create_arabic_trans_table()

logger = logging.getLogger(__name__)


class EasternArabicIntegerField(forms.IntegerField):
    """
    Subclass of IntegerField that accepts Eastern Arabic numeric
    characters too.
    """
    def to_python(self, value):
        if value is not None:
            value = value.translate(CONVERT_TO_WESTERN_DIGITS)
        return super(EasternArabicIntegerField, self).to_python(value)


class EasternArabicCharField(forms.CharField):
    """
    Subclass of CharField that accepts Eastern Arabic numeric
    characters, but converts them to Western Arabic numerals before storing.
    """
    def to_python(self, value):
        if value is not None:
            value = value.translate(CONVERT_TO_WESTERN_DIGITS)
        return super(EasternArabicCharField, self).to_python(value)


def validate_national_id(number):
    """
    Write our own validator so we can use a more meaningful
    error message.
    """
    msg_too_short = _("A National ID is a 12-digit number.")
    msg_too_long = _("A valid National ID is at most 12 digits long.")
    msg_first_char = _("A valid National ID starts with 1 or 2.")

    if number < MIN_NATIONAL_ID:
        raise ValidationError(msg_too_short)
    elif len(str(number)) > constants.NID_LENGTH:
        raise ValidationError(msg_too_long)
    elif number > MAX_NATIONAL_ID:
        raise ValidationError(msg_first_char)


class RegistrationQueryForm(forms.Form):
    national_id = EasternArabicIntegerField(
        validators=[validate_national_id],
        label=_("National ID"),
    )
    fbr_number = EasternArabicCharField(
        label=_("Family Book Record Number")
    )
    captcha = CaptchaField(
        label=_("Please type these numbers"),
        output_format="""
        <div class="third">%(image)s</div>
        <div class="two-thirds">%(hidden_field)s %(text_field)s</div>
        """
    )

    def clean_national_id(self):
        national_id = int(self.cleaned_data['national_id'])
        citizen = get_citizen_by_national_id(national_id)
        if not citizen:
            raise ValidationError(get_message(constants.NID_INVALID).msg)
        self.citizen = citizen
        return national_id

    def clean(self):
        # Check FBRN against citizen. We need the national ID to have already
        # been validated, so do it in the general form clean() method.
        citizen = getattr(self, 'citizen', None)
        if citizen and 'fbr_number' in self.cleaned_data \
                and citizen.fbr_number != self.cleaned_data['fbr_number']:
            raise ValidationError(get_message(constants.FBRN_MISMATCH).msg)
        return self.cleaned_data
