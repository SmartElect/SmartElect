from collections import namedtuple
import logging

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from dateutil.relativedelta import relativedelta

from .models import Case, FieldStaff, Update, CASE_ACTIONS, ALLOWED_ACTIONS
from .utils import get_group_choices
from civil_registry.utils import get_citizen_by_national_id
from libya_site.forms import validate_national_id, EasternArabicIntegerField
from libya_elections.form_utils import DateFieldWithPicker


logger = logging.getLogger(__name__)

DATE_FORM_FORMAT = '%Y-%m-%d'
INPUT_FORMATS = [DATE_FORM_FORMAT]

Grouping = namedtuple('Grouping', ['key', 'translated_name', 'order_by', 'key_select'])

# `key_select` is SQL we'll insert into the SELECT to set the value we want to use
# as the key for this report.

GROUP_BY_OPTIONS = (
    Grouping('days', _('Days of the week'), ['key_value'], "EXTRACT(dow from start_time)"),
    Grouping('hours', _('Hours of the day'), ['key_value'], "EXTRACT(hour from start_time)"),
    Grouping('day', _('Day'), ['key_value'], "DATE_TRUNC('day', start_time)"),
    Grouping('week', _('Week'), ['key_value'], "DATE_TRUNC('week', start_time)"),
    Grouping('month', _('Month'), ['key_value'], "DATE_TRUNC('month', start_time)"),
    Grouping('year', _('Year'), ['key_value'], "DATE_TRUNC('year', start_time)"),
    Grouping('op', _('Operator'), ['operator__last_name', 'operator__first_name'], 'operator_id'),
    Grouping('staff', _('Field staff'), ['field_staff__name'], "field_staff_id"),
)

GROUP_BY_CHOICES = [(opt.key, opt.translated_name) for opt in GROUP_BY_OPTIONS]
GROUP_BY_DICT = {opt.key: opt for opt in GROUP_BY_OPTIONS}


class GetStaffIDForm(forms.Form):
    staff_id = forms.CharField(
        label=_('Staff ID number'),
        min_length=3, max_length=3,
    )

    def clean_staff_id(self):
        if 'staff_id' in self.cleaned_data:
            try:
                staff_id = int(self.cleaned_data['staff_id'])
            except ValueError:
                raise ValidationError(_('Invalid staff ID format'))

            try:
                self.field_staff = FieldStaff.objects.get(
                    staff_id=staff_id,
                    suspended=False,
                )
            except FieldStaff.DoesNotExist:
                raise ValidationError(_('No active field staff with that ID'))
            else:
                return staff_id

    def update_case(self, case):
        case.field_staff = self.field_staff
        case.current_screen.input = self.cleaned_data['staff_id']

    def undo(self, case):
        case.field_staff = None
        case.current_screen.input = None


class GetNIDForm(forms.Form):
    national_id = EasternArabicIntegerField(
        label=_('National ID'),
        validators=[validate_national_id],
    )

    class Meta(object):
        model = Case
        fields = []

    def __init__(self, *args, **kwargs):
        super(GetNIDForm, self).__init__(*args, **kwargs)
        self.citizen = None

    def clean_national_id(self):
        national_id = int(self.cleaned_data['national_id'])
        citizen = get_citizen_by_national_id(national_id)
        if not citizen:
            raise ValidationError(_("That is not a valid National ID number."))
        self.citizen = citizen
        return national_id

    def update_case(self, case):
        assert self.citizen
        case.citizen = self.citizen
        case.current_screen.input = str(self.cleaned_data['national_id'])
        case.registration = self.citizen.registration

    def undo(self, case):
        case.citizen = None
        case.current_screen.input = ''
        case.registration = None


class SetUserGroupsMixin(object):
    def set_user_groups(self):
        """
        Set the user's help desk group based on the form input.
        """
        # Notice that we only add or remove groups that we had
        # offered as options on the form, and don't touch any other
        # groups that the user might belong to.
        for value, label in self.fields['help_desk_group'].choices:
            if value:
                group = Group.objects.get(name=value)
                if value in self.cleaned_data['help_desk_group']:
                    self.instance.groups.add(group)
                else:
                    self.instance.groups.remove(group)


class NewUserForm(SetUserGroupsMixin, UserCreationForm):
    help_desk_group = forms.fields.TypedChoiceField(
        required=False,
        choices=[
            # These are added on-the-fly depending on the permissions the user has
        ]
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'password1',
            'password2',
            'help_desk_group',
        ]

    def __init__(self, user, *args, **kwargs):
        super(NewUserForm, self).__init__(*args, **kwargs)
        self.fields['help_desk_group'].choices = get_group_choices(user)

    def save(self, commit=True):
        retval = super(NewUserForm, self).save(commit)
        if commit:
            self.set_user_groups()
        return retval


class UpdateUserForm(SetUserGroupsMixin, forms.ModelForm):
    """Form for updating a help desk user. Just like add user, except no password field."""
    help_desk_group = forms.fields.TypedChoiceField(
        required=False,
        choices=[
            # These are added on-the-fly depending on the permissions the user has
        ]
    )

    class Meta(object):
        model = User
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'help_desk_group',
        ]

    def __init__(self, user, *args, **kwargs):
        super(UpdateUserForm, self).__init__(*args, **kwargs)
        # Display the correct group
        user_groups = self.instance.groups.values_list('name', flat=True)
        choices = get_group_choices(user)
        self.fields['help_desk_group'].choices = choices
        initial_help_desk_groups = [value for value, label in choices
                                    if value in user_groups]
        if initial_help_desk_groups:
            self.initial['help_desk_group'] = initial_help_desk_groups[0]

    def save(self, commit=True):
        retval = super(UpdateUserForm, self).save(commit)
        if commit:
            self.set_user_groups()
        return retval


class AddCaseUpdateForm(forms.ModelForm):
    class Meta(object):
        model = Update
        fields = ['kind', 'reason_marked', 'recommended_action', 'comment']
        widgets = {
            'kind': forms.RadioSelect,
            'comment': forms.Textarea(attrs={'style': 'width: 100%'}),
        }

    def __init__(self, user, *args, **kwargs):
        super(AddCaseUpdateForm, self).__init__(*args, **kwargs)
        case = self.instance.case
        kind_name = dict(Update.UPDATE_KIND_CHOICES)

        kind_choices = [(Update.COMMENT, kind_name[Update.COMMENT])]
        if case.is_under_review():
            del self.fields['reason_marked']
            if user.has_perm('help_desk.recommend_case'):
                kind_choices.append((Update.RECOMMEND, kind_name[Update.RECOMMEND]))
                action_choices = [(action_name, dict(CASE_ACTIONS)[action_name])
                                  for action_name in ALLOWED_ACTIONS[case.reason_marked]]
                self.fields['recommended_action'].choices = action_choices
            else:
                del self.fields['recommended_action']
            if user.has_perm('help_desk.resolve_case'):
                kind_choices.append((Update.RESOLVE, kind_name[Update.RESOLVE]))
        else:
            del self.fields['recommended_action']
            if user.has_perm('help_desk.mark_case'):
                kind_choices.append((Update.MARK_FOR_REVIEW, kind_name[Update.MARK_FOR_REVIEW]))
            else:
                del self.fields['reason_marked']

        self.fields['kind'].choices = kind_choices

    def clean(self):
        if not self.cleaned_data.get('comment', ''):
            # No comment? Do we need one for this?
            kind = self.cleaned_data.get('kind', '')
            reason = self.cleaned_data.get('reason_marked', '')
            if kind == 'comment' or (kind == 'mark' and reason == 'other'):
                raise ValidationError(_('A comment is required'))
        return self.cleaned_data

    def save(self, commit=True):
        update = self.instance
        case = update.case
        should_save_case = True
        if update.kind == Update.MARK_FOR_REVIEW:
            case.review_classification = Case.FOR_REVIEW
            case.reason_marked = self.cleaned_data['reason_marked']
        elif update.kind == Update.RECOMMEND:
            case.review_classification = Case.RECOMMENDED
            case.recommended_action = self.cleaned_data['recommended_action']
        elif update.kind == Update.RESOLVE:
            case.review_classification = Case.RESOLVED
        else:
            should_save_case = False
        if should_save_case and commit:
            case.save()
        return super(AddCaseUpdateForm, self).save(commit)


class BaseCaseForm(forms.Form):
    STATUS_CHOICES = (
        ('any', _('any')),
        ('open', _('in progress')),
        ('marked', _('review required')),
        ('recommended', _('action required')),
        ('complete', _('complete')),
    )

    CALL_MADE_BY_CHOICES = (
        ('any', _('any')),
        ('staff', _('staff')),
        ('citizen', _('citizen')),
    )

    from_date = DateFieldWithPicker(label=_('From date'), required=True)
    to_date = DateFieldWithPicker(label=_('To date'), required=True)
    status = forms.ChoiceField(label=_('Call status'),
                               choices=STATUS_CHOICES)
    call_made_by = forms.ChoiceField(label=_('Call made by'),
                                     choices=CALL_MADE_BY_CHOICES)

    def clean(self):
        from_date = self.cleaned_data.get('from_date', None)
        to_date = self.cleaned_data.get('to_date', None)
        if from_date and to_date and from_date > to_date:
            raise forms.ValidationError(
                _('The ending date must exceed the beginning date.'))
        self.from_date = self.cleaned_data.get('from_date', '')
        self.to_date = self.cleaned_data.get('to_date', '')
        self.to_date = self.to_date + relativedelta(days=1) if self.to_date else self.to_date
        return self.cleaned_data


class StatisticsReportForm(BaseCaseForm):
    group_by = forms.ChoiceField(label='Group By', choices=GROUP_BY_CHOICES)
    data_to_show = forms.ChoiceField(
        label=_('Data to show'),
        choices=(
            ('number', _('Number of calls')),
            ('length', _('Average length of calls in seconds')),
        ),
    )


class IndividualCasesReportForm(BaseCaseForm):
    call_outcomes = forms.MultipleChoiceField(
        label=_('Call outcomes'),
        choices=Case.CALL_OUTCOME_CHOICES,
        widget=forms.SelectMultiple(
            attrs={
                'size': len(Case.CALL_OUTCOME_CHOICES),
                }
        )
    )
