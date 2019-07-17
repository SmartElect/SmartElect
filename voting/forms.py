# Python imports
import datetime
import logging

# Django imports
from django.forms import ModelForm, HiddenInput
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

# 3rd party imports
from pytz import timezone

# This project's imports
from .models import RegistrationPeriod
from libya_elections.form_utils import DateFieldWithPicker, TimeFieldWithPicker


logger = logging.getLogger(__name__)


def validate_headers(reader, expected):
    """
    Validate the CSV DictReader has the expected headers.

    :param reader: A csv DictReader
    :param expected: list of header titles
    :return: a list of error messages. If list is empty, the headers are all valid.
    """
    err_msgs = []
    headers = reader.fieldnames

    if len(headers) != len(expected):
        err_msgs.append(
            _("Found {} header columns, but expected {}.").format(
                len(headers), len(expected)))
        return err_msgs

    for i, expected_header in enumerate(expected):
        header = headers[i]
        if header.lower() != expected_header.lower():
            err_msgs.append(
                _("Expected header {} but found {}.").format(
                    expected_header, header))
    # normalize headers in case capitalization is different
    reader.fieldnames = expected
    return err_msgs


def split_datetime(a_datetime):
    """Given a datetime.datetime, return a 2-tuple of (datetime.date, datetime.time)."""
    return (a_datetime.date(), a_datetime.time())


class RegistrationPeriodAddForm(ModelForm):
    """RegistrationPeriod Add/Edit form that implements date/time pickers and custom validation."""
    # The basic strategy for handling dates & times here is to split the DateTime fields into
    # date & time fields during init and then stitch them back together again during clean().

    get_help_text = lambda field_name: RegistrationPeriod._meta.get_field(field_name).help_text

    start_date_only = DateFieldWithPicker(required=True,
                                          label=_('Start date'),
                                          help_text=get_help_text('start_time'))
    start_time_only = TimeFieldWithPicker(required=True,
                                          label=_('Start time'),
                                          help_text=get_help_text('start_time'))
    end_date_only = DateFieldWithPicker(required=True,
                                        label=_('End date'),
                                        help_text=get_help_text('end_time'))
    end_time_only = TimeFieldWithPicker(required=True,
                                        label=_('End time'),
                                        help_text=get_help_text('end_time'))

    class Meta:
        model = RegistrationPeriod

        # Fields must include start_time and end_time fields even though
        # they're always hidden. They must be present on the form, otherwise
        # their values will not be passed to the model's clean() method during
        # validation.
        fields = ['start_date_only', 'start_time_only',
                  'end_date_only', 'end_time_only',
                  # These are the 2 hidden fields.
                  'start_time', 'end_time',
                  ]
        widgets = {'start_time': HiddenInput(),
                   'end_time': HiddenInput(),
                   }

    def __init__(self, *args, **kwargs):
        registration_period = kwargs.get('instance', None)

        kwargs['initial'] = kwargs.get('initial', {})
        if registration_period:
            # Split DateTime fields into date & time
            tz = timezone(settings.TIME_ZONE)

            if registration_period.start_time:
                date, time = split_datetime(registration_period.start_time.astimezone(tz))
                kwargs['initial']['start_date_only'] = date
                kwargs['initial']['start_time_only'] = time
            if registration_period.end_time:
                date, time = split_datetime(registration_period.end_time.astimezone(tz))
                kwargs['initial']['end_date_only'] = date
                kwargs['initial']['end_time_only'] = time

        super(RegistrationPeriodAddForm, self).__init__(*args, **kwargs)

        self.fields['start_time'].required = False
        self.fields['end_time'].required = False

    def clean(self):
        cleaned_data = super(RegistrationPeriodAddForm, self).clean()

        if self.errors:
            # Since there's already errors, don't bother doing any custom validation.
            return cleaned_data

        # Combine the discrete date and time fields into datetime values and populate
        # the respective hidden DateTime fields with the combined values.
        tz = timezone(settings.TIME_ZONE)

        # Create an alias to make this code a little more readable.
        combine = datetime.datetime.combine

        if not self.errors:
            # Combine date & time fields into DateTimes.
            cleaned_data['start_time'] = \
                combine(cleaned_data['start_date_only'],
                        cleaned_data['start_time_only'])
            cleaned_data['end_time'] = \
                combine(cleaned_data['end_date_only'],
                        cleaned_data['end_time_only'])

            # Localize times.
            cleaned_data['start_time'] = tz.localize(cleaned_data['start_time'])
            cleaned_data['end_time'] = tz.localize(cleaned_data['end_time'])

        return cleaned_data
