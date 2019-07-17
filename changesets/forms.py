from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from selectable.forms import AutoCompleteSelectField, AutoCompleteSelectMultipleField

from civil_registry.utils import get_citizen_by_national_id
from libya_elections.constants import NID_LENGTH
from register.lookups import RegistrationCenterLookup

from .models import Changeset


MAX_ERRORS = 10


class ChangesetForm(forms.ModelForm):
    """
    Form for creating or editing a Changeset.

    Uses django-selectable for autocompleting selection of registration centers,
    and some javascript in the page to implement custom behavior as the user
    changes their choices.
    """
    selected_centers = AutoCompleteSelectMultipleField(
        help_text=_("Start typing registration center name to add to list"),
        label=_("Selected centers"),
        lookup_class=RegistrationCenterLookup,
        required=False,
    )

    target_center = AutoCompleteSelectField(
        help_text=_("Start typing registration center name to choose"),
        lookup_class=RegistrationCenterLookup,
        required=False,
    )

    upload_file = forms.FileField(
        required=False,
        help_text=_("Upload text file with one NID per line, and no headers or punctuation.")
    )

    okay_to_remove_approvals = forms.BooleanField(
        required=True,
        help_text=_("This changeset has one or more approvals. If you change the changeset, "
                    "the approvals will be revoked and the changeset will have to be approved "
                    "again. If you want to do that, check here. If not, cancel, or go to "
                    "another page without submitting your changes.")
    )

    # Django will add this class to required fields.
    # Starting in Django 1.8, it'll add it to their labels too, but we're
    # still on 1.7 so we'll have to do it in the template.
    required_css_class = 'requiredField'

    class Meta(object):
        fields = [
            'name',
            'change',
            'how_to_select',
            'upload_file',
            'selected_centers',
            'other_changeset',
            'target_center',
            'message',
            'justification',
        ]
        model = Changeset

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super(ChangesetForm, self).__init__(*args, **kwargs)
        self.citizens = []  # Citizens from uploaded file

        # If there are no approvals or no changeset yet,
        # remove the 'okay_to_remove_approvals' field
        if not (self.instance and self.instance.number_of_approvals):
            del self.fields['okay_to_remove_approvals']

    def clean_other_changeset(self):
        """Ensure other_changeset is provided if needed, and in an acceptable status"""
        data = self.cleaned_data
        other_changeset = data.get('other_changeset', None)
        if (data['how_to_select'] == Changeset.SELECT_OTHER_CHANGESET
                and not other_changeset):
            raise ValidationError(_("No other changeset selected"))
        if data['change'] == Changeset.CHANGE_ROLLBACK:
            if not other_changeset:
                raise ValidationError(_("No other changeset selected"))
            if other_changeset.status not in (Changeset.STATUS_SUCCESSFUL,
                                              Changeset.STATUS_PARTIALLY_SUCCESSFUL):
                raise ValidationError(_("Only successful changesets can be rolled back."))
        return other_changeset

    def clean_selected_centers(self):
        """Ensure selected_centers are provided if needed"""
        data = self.cleaned_data
        if data['how_to_select'] == Changeset.SELECT_CENTERS and not data['selected_centers']:
            raise ValidationError(_("No centers selected"))
        return data['selected_centers']

    def clean_target_center(self):
        """Ensure target center is provided if needed, and is not one of the source centers"""
        data = self.cleaned_data
        if data['change'] == Changeset.CHANGE_CENTER:
            if not data['target_center']:
                raise ValidationError(_("No target center selected"))
            if (data['how_to_select'] == Changeset.SELECT_CENTERS
                    and data['target_center'] in data.get('selected_centers', [])):
                raise ValidationError(_("Target center is one of the centers being moved from"))
        return data['target_center']

    def clean_upload_file(self):
        """Handle uploading a file of NIDs. Will validate the input, look up the citizens, and
        set self.citizens to a list of the Citizen objects they chose."""
        data = self.cleaned_data
        if data['how_to_select'] == Changeset.SELECT_UPLOADED_NIDS:
            uploaded_file = data['upload_file']
            if not uploaded_file:
                if self.instance.pk and self.instance.uploaded_citizens.exists():
                    # It's okay not to re-upload citizens, we already have some
                    return
                raise ValidationError(
                    _("An uploaded file is required if selection method is uploaded NIDs"))
            errors = []
            for i, line in enumerate(uploaded_file):
                line_number = i + 1  # Humans start counting at 1, not 0
                if len(errors) >= MAX_ERRORS:
                    errors.append(_("Stopping after {number} errors.").format(number=len(errors)))
                    break
                line = line.decode().strip()
                if not line:
                    # Allow and ignore blank lines
                    continue
                if len(line) != NID_LENGTH:
                    errors.append(_("Line {number}: Wrong length").format(number=line_number))
                    continue
                try:
                    num = int(line)
                except (ValueError, TypeError):
                    errors.append(_("Line {number}: Not a valid number").format(number=line_number))
                    continue
                if line[0] not in ['1', '2']:
                    errors.append(
                        _("Line {number}: Not a valid national ID number")
                        .format(number=line_number))
                    continue
                citizen = get_citizen_by_national_id(num)
                if not citizen:
                    errors.append(
                        _("Line {number}: No person registered with that NID")
                        .format(number=line_number))
                    continue
                self.citizens.append(citizen)
            if errors:
                raise ValidationError(". ".join(errors))
        return data['upload_file']

    def save(self, *args, **kwargs):
        """
        Save the Changeset, and set selected_citizens based on self.citizens
        """
        # If new, remember who created it
        if not self.instance.pk:
            self.instance.created_by = self.request.user
        changeset = super(ChangesetForm, self).save(*args, **kwargs)
        if changeset.pk:
            # Remove any citizens from a previous edit that are no longer on the list.
            citizens_to_remove = set(changeset.selected_citizens.all()) - set(self.citizens)
            changeset.selected_citizens.remove(*citizens_to_remove)
            # Add any new ones
            citizens_to_add = set(self.citizens) - set(changeset.selected_citizens.all())
            changeset.selected_citizens.add(*citizens_to_add)
        # If there were any approvals, remove them (and update status)
        for approving_user in changeset.approvers.all():
            changeset.revoke_approval(approving_user)
            if self.request:
                messages.info(self.request,
                              _("Approval of {user} removed due to changes").
                              format(user=approving_user))
        return changeset
