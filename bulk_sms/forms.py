import os

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from .models import Batch, Broadcast
from .tasks import upload_bulk_sms_file
from .utils import save_uploaded_file, validate_uploaded_file


INVALID_ENCODING = _('The uploaded file had invalid characters. '
                     'Please be sure that it is saved as UTF-8.')


class UploadBulkSMSesForm(forms.ModelForm):
    """Form for uploading a CSV that contains messages for many individual recipients.

    Each recipient's message is specified in the CSV, so each can get the same message, a custom
    message, or some mix.
    """
    csv = forms.FileField()

    class Meta:
        model = Batch
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': _('Name for this bulk SMS broadcast.')}),
            'description': forms.Textarea(
                attrs={'placeholder': _('Describe this bulk SMS broadcast')}),
        }

    def clean_csv(self):
        # Is uploaded file valid?
        csv = self.cleaned_data['csv']
        self.temp_file_path = save_uploaded_file(csv)
        try:
            validate_uploaded_file(self.temp_file_path)
        except ValidationError:
            os.remove(self.temp_file_path)
            raise
        except UnicodeDecodeError:
            os.remove(self.temp_file_path)
            raise ValidationError(INVALID_ENCODING)
        # Leaves file in self.temp_file_path
        return csv

    def save(self, *args, **kwargs):
        """
        Save the form, set its status to PROCESSING, and kick off a celery task
        to process the uploaded file creating all the records.
        Return the new Batch.
        """
        batch = super(UploadBulkSMSesForm, self).save(*args, **kwargs)
        batch.status = Batch.UPLOADING
        batch.save()
        # create a broadcast for this upload
        Broadcast.objects.create(
            created_by=batch.created_by,
            batch=batch,
            audience=Broadcast.CUSTOM,
            message="Individual messages uploaded in CSV file."
        )
        upload_bulk_sms_file.delay(batch.id, self.temp_file_path)
        return batch


class BroadcastForm(forms.ModelForm):
    """Form for creating bulk SMSes that broadcast the same message to recipients in a group"""
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super(BroadcastForm, self).__init__(*args, **kwargs)
        self.fields['audience'] = forms.ChoiceField(choices=Broadcast.MINIMUM_AUDIENCE)

    class Meta:
        model = Broadcast
        fields = ['audience', 'center', 'message']

    def clean_center(self):
        audience = self.cleaned_data.get('audience')
        center = self.cleaned_data.get('center')
        if audience == Broadcast.SINGLE_CENTER and not center:
            raise forms.ValidationError(_("This field is required."))
        return center

    def save(self):
        self.instance.created_by = self.user
        self.instance.save()
