# Python imports
import re

# Django imports
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

# Project imports
from register.models import Office, RegistrationCenter, Constituency
from rollgen.constants import JOB_NAME_REGEX
from rollgen.job import PHASES
from rollgen.utils import is_rollgen_output_dir, validate_comma_delimited_ids, \
    find_invalid_center_ids

EM_DASH = '\u2014'

_JOB_NAME_REGEX = re.compile('^' + JOB_NAME_REGEX + '$')


class CommaDelimitedCenterIdFormField(forms.CharField):
    """A textbox that limits input to a comma-delimited list of ints that look like center ids.

    Whitespace is allowed. Trailing commas are ignored. The center ids are not checked against the
    database.

    It returns a list of ints.
    """
    message = _("Please enter a comma-delimited list of center ids.")

    def to_python(self, value):
        if value is None:
            value = ''
        # Remove whitespace and trailing commas; they're valid and meaningless.
        value = value.replace(' ', '')
        value = value.rstrip(',')

        if value:
            validate_comma_delimited_ids(value, True)
            return list(map(int, value.split(',')))
        else:
            return []


def validate_job_name(text):
    """Raise ValidationError if the name fails to meet a few not-very-restrictive criteria."""
    stripped = text.strip()

    if not _JOB_NAME_REGEX.match(stripped):
        raise ValidationError(_('"%(name)s" is not a valid job name.'), params={'name': text})
    if is_rollgen_output_dir(stripped):
        raise ValidationError(_('There is already a job named "%(name)s".'), params={'name': text})


class NewJobForm(forms.Form):
    name = forms.CharField(validators=[validate_job_name], required=True, min_length=1,
                           max_length=200,
                           help_text=_('There are no restrictions on job names except that they '
                                       'may not begin with a period and may not '
                                       'contain back nor forward slashes.'))
    phase_choices = [(None, '------'), ] + [(k, v) for k, v in PHASES.items()]
    phase = forms.ChoiceField(choices=phase_choices, required=True)
    forgive_no_office = forms.BooleanField(required=False,
                                           label=_("Accept centres with no office"))
    forgive_no_voters = forms.BooleanField(required=False,
                                           label=_("Accept centres with no voters"))
    center_selection_type_choices = \
        (('all', _('All centres')),
         ('by_constituency', _('The centres in the constituencies selected below ') + EM_DASH),
         ('by_office', _('The centres in the offices selected below ') + EM_DASH),
         ('by_center_select_list', _('The centres selected below ') + EM_DASH),
         ('by_center_text_list', _('The centres in this comma-delimited list ') + EM_DASH),
         )
    center_selection_type = forms.ChoiceField(choices=(center_selection_type_choices),
                                              widget=forms.RadioSelect, required=True)
    offices = forms.ModelMultipleChoiceField(queryset=Office.objects.all(), required=False)
    constituencies = forms.ModelMultipleChoiceField(queryset=Constituency.objects.all(),
                                                    required=False)
    qs = RegistrationCenter.objects.filter(reg_open=True)
    center_select_list = forms.ModelMultipleChoiceField(queryset=qs, required=False)
    center_text_list = CommaDelimitedCenterIdFormField(required=False)

    def clean_name(self):
        return self.cleaned_data['name'].strip()

    def clean(self):
        if 'center_selection_type' in self.cleaned_data:
            center_selection_type = self.cleaned_data['center_selection_type']

            if center_selection_type == 'by_constituency':
                # At least one constituency must be selected
                if not self.cleaned_data['constituencies']:
                    self.add_error('constituencies',
                                   ValidationError(_('You must select at least one constituency.')))
            elif center_selection_type == 'by_office':
                # At least one office must be selected
                if not self.cleaned_data['offices']:
                    self.add_error('offices',
                                   ValidationError(_('You must select at least one office.')))
            elif center_selection_type == 'by_center_select_list':
                # At least one center must be selected
                if not self.cleaned_data['center_select_list']:
                    self.add_error('center_select_list',
                                   ValidationError(_('You must select at least one centre.')))
            elif center_selection_type == 'by_center_text_list':
                # At least one center must be entered
                center_text = self.cleaned_data.get('center_text_list', '')
                if center_text:
                    invalid_center_ids = find_invalid_center_ids(center_text)
                    if invalid_center_ids:
                        invalid_center_ids = ', '.join(map(str, invalid_center_ids))
                        msg = _("These centre ids are invalid: {}").format(invalid_center_ids)
                        self.add_error('center_text_list', ValidationError(msg))
                else:
                    # Center text is empty or didn't validate
                    if 'center_text_list' not in self.errors:
                        self.add_error('center_text_list',
                                       ValidationError(_('You must enter at least one centre.')))

        # else:
            # center_selection_type is required, so user will get an error.
