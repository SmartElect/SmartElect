import re

from django.core.exceptions import ValidationError
from django import forms
from django.utils.translation import ugettext as _

from text_messages.models import MessageText


# Placeholders could be {NAME} or %(NAME)s or %(NAME)d
PLACEHOLDER_RE_BRACES = re.compile(r'{\S+}')
PLACEHOLDER_RE_PERCENTS = re.compile(r'%\(\S+\)[sd]')


def get_braces_placeholders(msg):
    return PLACEHOLDER_RE_BRACES.findall(msg)


def get_percents_placeholders(msg):
    return PLACEHOLDER_RE_PERCENTS.findall(msg)


def get_placeholders(msg):
    return get_braces_placeholders(msg) or get_percents_placeholders(msg)


def validate_one_kind_of_placeholder_in_message(msg):
    """
    Raise ValidationError if msg has more than one kind of placeholder
    """
    if get_braces_placeholders(msg) and get_percents_placeholders(msg):
        raise ValidationError(_("Messages should use either {} placeholders or %()s "
                                "placeholders but not both"))


def validate_same_kind_of_placeholders_in_two_messages(en, ar):
    if ((get_braces_placeholders(en) and get_percents_placeholders(ar)) or
            (get_percents_placeholders(en) and get_braces_placeholders(ar))):
        raise ValidationError(_("English and Arabic messages must use the same kind of "
                                "placeholders, either {} or %()s"))


class MessageTextForm(forms.ModelForm):
    class Meta(object):
        fields = ['description', 'msg_en', 'msg_ar', 'enhanced_en', 'enhanced_ar']
        model = MessageText

    def clean_msg_en(self):
        validate_one_kind_of_placeholder_in_message(self.cleaned_data['msg_en'])
        return self.cleaned_data['msg_en']

    def clean_msg_ar(self):
        validate_one_kind_of_placeholder_in_message(self.cleaned_data['msg_ar'])
        return self.cleaned_data['msg_ar']

    def clean_enhanced_en(self):
        validate_one_kind_of_placeholder_in_message(self.cleaned_data['enhanced_en'])
        return self.cleaned_data['enhanced_en']

    def clean_enhanced_ar(self):
        validate_one_kind_of_placeholder_in_message(self.cleaned_data['enhanced_ar'])
        return self.cleaned_data['enhanced_ar']

    def clean(self):
        """
        Raise a ValidationError if an Arabic translation is missing any of
        the placeholders ({NAME}) that the English message has.
        """
        data = self.cleaned_data
        for key in ['msg', 'enhanced']:
            en = data.get('%s_en' % key, False)
            ar = data.get('%s_ar' % key, False)
            if en and ar:
                validate_same_kind_of_placeholders_in_two_messages(en, ar)
                if set(get_placeholders(en)) != set(get_placeholders(ar)):
                    raise ValidationError(_("The Arabic text must have the same placeholders "
                                            "as the English text."))
        return data
