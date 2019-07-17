import logging

from django import forms
from django.utils.translation import ugettext_lazy as _

from .models import Blacklist, Whitelist, Office, Constituency, RegistrationCenter, SubConstituency
from libya_elections.phone_numbers import canonicalize_phone_number


CSV_FIELDS = ['center_id', 'name', 'copy_of_id', 'region_name', 'office_id', 'office_name',
              'constituency_name', 'constituency_id', 'subconstituency_id', 'subconstituency_name',
              'mahalla_name', 'village_name', 'center_type', 'center_lat', 'center_lon', ]
NONMODEL_FIELDS = ['region_name', 'office_name', 'constituency_name', 'subconstituency_name']

logger = logging.getLogger(__name__)


class UploadCenterForm(forms.Form):
    csv = forms.FileField(required=True, label=_("CSV File"))

    def process(self):
        """Handles the uploaded csv file and updates the ecc table"""
        # Avoid circular import since utils needs to import RegistrationCenterCSVForm
        from .utils import update_center_table
        csv = self.cleaned_data['csv']
        msg = update_center_table(csv)
        logger.debug("Result of processing upload: %s" % (msg,))
        return msg


class RegistrationCenterCSVForm(forms.ModelForm):
    copy_of_id = forms.IntegerField(required=False)
    office_id = forms.IntegerField()
    constituency_id = forms.IntegerField()
    subconstituency_id = forms.IntegerField()
    center_type = forms.CharField()

    class Meta:
        model = RegistrationCenter
        # Form validation presents us with a bit of a Catch-22. The FK fields (copy_of, office,
        # etc.) must be present in self.fields otherwise they won't be set when
        # RegistrationCenter.clean() is called. However they are not in the CSV and must be
        # inferred from the corresponding xxx_id field. We instruct Django to validate the _id
        # field first in the clean_xxx_id() method and then set the corresponding data['xxx']
        # value so it looks to Django as if the user 'submitted the form' with the 'xxx' field
        # set properly.
        fields = ['copy_of_id', 'copy_of', 'office_id', 'office', 'constituency_id', 'constituency',
                  'subconstituency_id', 'subconstituency', ]
        skip_these = fields + NONMODEL_FIELDS
        for f in CSV_FIELDS:
            if f not in skip_these:
                fields.append(f)

    # Note: These validators are specific to the RegistrationCenter CSV upload process.
    #       Additional validators exist in the RegistrationCenter model which are applied both here
    #       and for admin forms.

    def clean(self):
        center_id = self.cleaned_data.get('center_id', 0)
        try:
            center = RegistrationCenter.objects.get(center_id=center_id)
        except RegistrationCenter.DoesNotExist:
            center = None

        if self.has_changed() and center and center.copy_of:
            raise forms.ValidationError(_('Copy centres are read-only.'))

    def clean_name(self):
        """
        Ensure that there are no newlines in the name. This is not needed in the admin because you
        can't insert newlines in a CharField
        """
        if '\n' in self.cleaned_data['name']:
            raise forms.ValidationError(_('Newlines are not allowed.'))
        return self.cleaned_data['name']

    def clean_center_type(self):
        """Map the string (Arabic or English) in the center_type column to an integer value"""
        center_types = RegistrationCenter.Types

        center_type_from_user = self.cleaned_data['center_type']
        center_type = center_types.NAMES_REVERSED['ar'].get(center_type_from_user, None)
        if not center_type:
            # Not Arabic? Maybe it's English
            center_type = center_types.NAMES_REVERSED['en'].get(center_type_from_user, None)

        if center_type:
            return center_type
        else:
            # Center type from user matched neither the Arabic nor English center types.
            choice_names = ['%s (%s)' % (name_ar, name_en)
                            for (value_ar, name_ar), (value_en, name_en) in
                            zip(center_types.get_choices('ar'), center_types.get_choices('en'))]
            raise forms.ValidationError(
                _('That is not a valid center_type. Valid choices are {choice_names}.').format(
                    choice_names=', '.join(choice_names)))

    def clean_copy_of_id(self):
        """
        Ensure that if the (optional) copy_of_id is provided,
        it points to an existing center
        """
        # Note that in this context 'copy_of_id' refers to center.center_id, not center.id.
        proposed_copy_of_id = self.cleaned_data.get('copy_of_id', 0)
        proposed_copy_of_id = 0 if proposed_copy_of_id is None else proposed_copy_of_id

        if proposed_copy_of_id:
            # For both existing and new centers, the copy center must exist. There shouldn't be any
            # way for a copy center to disappear once another center has been associated with it,
            # so this check should be unnecessary for existing centers.
            try:
                copy_of_center = RegistrationCenter.objects.get(center_id=proposed_copy_of_id)
            except RegistrationCenter.DoesNotExist:
                raise forms.ValidationError(_('Copy centre does not exist.'))

            # also set data['copy_of'] so Django doesn't try to use the default value
            self.data['copy_of'] = copy_of_center.id
        else:
            self.data['copy_of'] = None
        return proposed_copy_of_id

    def clean_office_id(self):
        """Ensure that the office_id refers to an existing office"""
        office_id = self.cleaned_data['office_id']
        try:
            Office.objects.get(id=office_id)
        except Office.DoesNotExist:
            raise forms.ValidationError(_('Office does not exist.'))
        # also set data['office'] so Django doesn't try to use the default value
        self.data['office'] = office_id
        return office_id

    def clean_constituency_id(self):
        """Ensure that the constituency_id refers to an existing constituency"""
        constituency_id = self.cleaned_data['constituency_id']
        try:
            Constituency.objects.get(id=constituency_id)
        except Constituency.DoesNotExist:
            raise forms.ValidationError(_('Constituency does not exist.'))
        # also set data['constituency'] so Django doesn't try to use the default value
        self.data['constituency'] = constituency_id
        return constituency_id

    def clean_subconstituency_id(self):
        """Ensure that the subconstituency_id refers to an existing subconstituency"""
        subconstituency_id = self.cleaned_data['subconstituency_id']
        try:
            SubConstituency.objects.get(id=subconstituency_id)
        except SubConstituency.DoesNotExist:
            raise forms.ValidationError(_('Subconstituency does not exist.'))
        # also set data['subconstituency'] so Django doesn't try to use the default value
        self.data['subconstituency'] = subconstituency_id
        return subconstituency_id


class NamedThingAbstractForm(forms.ModelForm):
    def clean_name_english(self):
        name = self.cleaned_data.get('name_english', '')
        return name

    def clean_name_arabic(self):
        name = self.cleaned_data.get('name_arabic', '')
        return name


class OfficeForm(NamedThingAbstractForm):
    class Meta:
        model = Office
        exclude = ('deleted',)

    def __init__(self, *args, **kwargs):
        super(OfficeForm, self).__init__(*args, **kwargs)
        self.fields['region'].choices = Office.REGION_CHOICES


class ConstituencyForm(NamedThingAbstractForm):
    class Meta:
        model = Constituency
        exclude = ('deleted',)


class SubConstituencyForm(NamedThingAbstractForm):
    class Meta:
        model = SubConstituency
        exclude = ('deleted',)


class RegistrationCenterEditForm(forms.ModelForm):
    """Form for adding/editing reg centers. Hides copy_of as appropriate."""
    class Meta:
        model = RegistrationCenter
        exclude = ('deleted',)

    def __init__(self, *args, **kwargs):
        center = kwargs.get('instance', None)

        super(RegistrationCenterEditForm, self).__init__(*args, **kwargs)

        if center and (center.center_type != RegistrationCenter.Types.COPY):
            # If this isn't already a copy center, it can't become one, and the only valid value
            # for copy_of is None. Any change the user would make to copy_of would result in an
            # error so it's best not to display it at all.
            del self.fields['copy_of']

        for fieldname in ['office', 'constituency', 'subconstituency']:
            self.fields[fieldname].queryset = self.fields[fieldname].queryset.all()
        self.fields['center_type'].choices = RegistrationCenter.Types.CHOICES


class BlackWhiteListedNumbersUploadForm(forms.Form):
    """Handles upload of bulk black/whitelisted numbers"""
    import_file = forms.FileField(required=True,
                                  allow_empty_file=True,
                                  help_text=_("Upload a text file, one phone number per line."))


class BlackWhiteListedNumberEditForm(forms.ModelForm):
    """Blacklist and Whitelist forms subclass this base form"""

    class Meta:
        # This form can't be used directly; it must be subclassed.
        model = None

    def __init__(self, *args, **kwargs):
        """Remove nondigits from phone_number during init of the edit form.

        Have to do it before the validation, because it'll run the field
        validation before we can get control, and numbers with non-digits
        won't pass.
        """
        if kwargs['data']:
            # This is a POST, leave the data as-is.
            pass
        else:
            if 'instance' in kwargs:
                # User is editing an existing number.
                kwargs['data'] = {}
                kwargs['data']['phone_number'] = \
                    canonicalize_phone_number(kwargs['instance'].phone_number)
            # else:
                # User is adding a new number; nothing to reformat.

        super(BlackWhiteListedNumberEditForm, self).__init__(*args, **kwargs)


class BlacklistedNumberEditForm(BlackWhiteListedNumberEditForm):
    class Meta:
        model = Blacklist
        fields = ['phone_number']


class WhitelistedNumberEditForm(BlackWhiteListedNumberEditForm):
    class Meta:
        model = Whitelist
        fields = ['phone_number']
