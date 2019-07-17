from django import forms
from django.conf import settings
from django.utils.translation import ugettext_lazy as _


class MessageForm(forms.Form):
    identity = forms.CharField(label=_("From"), max_length=15)

    to_addr = forms.ChoiceField(
        label=_("Shortcode"),
        choices=[(short_code, short_code) for short_code in settings.SHORT_CODES])

    text = forms.CharField(label=_("Message"), required=False)

    bulk = forms.FileField(
        label=_("Multiple Messages"),
        required=False,
        help_text=_("Alternatively, upload a <em>plain text file</em> "
                    "containing a single message per line."))

    def clean_identity(self):
        if 'identity' in self.cleaned_data:
            identity = self.cleaned_data['identity'].strip()
            if not identity.isnumeric():
                raise forms.ValidationError(_("Phone number must be all numeric."))
            return identity
