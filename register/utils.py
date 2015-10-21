# -*- coding: utf-8 -*-
# Python imports
from __future__ import unicode_literals
from datetime import timedelta, datetime, time
from functools import wraps
import logging

# Django imports
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe
from django.utils.translation import override, ugettext_lazy as _

# 3rd party imports
from pytz import timezone

# This project's imports
from .forms import RegistrationCenterCSVForm, CSV_FIELDS
from .models import Blacklist, Whitelist, Registration, RegistrationCenter
from libya_elections.constants import CENTER_ID_MAX_INT_VALUE, CENTER_ID_MIN_INT_VALUE
from libya_elections.csv_utils import UnicodeReader
from libya_elections.phone_numbers import canonicalize_phone_number
from voting.models import Election, RegistrationPeriod

logger = logging.getLogger(__name__)

STATUS_MESSAGE = _(
    "Imported {created} new centers. Updated {updated} centers. "
    "There were {dupes} duplicates skipped. Blank rows {blank}")
ERRORS_OCCURRED_MESSAGE = _(
    "Errors occurred while parsing the uploaded file. No centers were imported or updated."
)
PARSING_ERROR = _(
    "Error found in line {line_number}: row does not contain the exact number of columns "
    "required or it contains blank lines. The row should only have the following "
    " columns: {columns}.")
FORM_FIELD_ERROR = _(
    'Error in row {line_number}. Field: {field_name}. Value: {value}. Error: {error}')
FORM_ERROR = _(
    'Error in row {line_number}. Error: {error}')

MIDNIGHT = time(0, 0, 0)


def registration_in_progress(as_of=None):
    return RegistrationPeriod.objects.in_progress(as_of=as_of)


def registration_allowed(msg):
    """
    Return True if registration is allowed in any form:
      - Regular (Tool 1) registration
      - Registration changes during SMS Polling (for selected voters)
        - These voters will have msg.fields['registration_allowed'] set to True
    """
    return (tool_1_enabled() or
            msg.fields.get('registration_allowed'))


def tool_1_enabled(as_of=None):
    """SMS voter registration"""
    return settings.ENABLE_ALL_TOOLS \
        or registration_in_progress(as_of)


def addressed_to_us(func):
    """Handles messages that are addressed to us."""
    @wraps(func)
    def wrapper(cls, router, msg):
        if cls.is_addressed_to_us(msg):
            return func(cls, router, msg)
    return wrapper


def center_checkin_times(election):
    """The center check-in time starts at midnight local time, 2 days before polling starts,
    and ends at the end of polling.

    Return the start and stop times for check-in.
    """
    two_days_before = election.polling_start_time.date() - timedelta(days=2)
    tz = timezone(settings.TIME_ZONE)
    activation_start = tz.localize(datetime.combine(two_days_before, MIDNIGHT))
    return activation_start, election.polling_end_time


def center_opening_enabled(as_of=None):
    """
    The center opening period is from midnight, two days before polling starts,
    to the end of polling, for in-person elections.

    (This can be overridden by ENABLE_ALL_TOOLS.)
    """
    return (settings.ENABLE_ALL_TOOLS
            or Election.objects.get_elections_with_center_opening_enabled(as_of).exists())


def phone_activation_enabled(as_of=None):
    """
    The phone activation period is from midnight, two days before polling starts,
    to the end of polling.

    (This can be overridden by ENABLE_ALL_TOOLS.)
    """
    return (settings.ENABLE_ALL_TOOLS
            or Election.objects.get_elections_with_phone_activation_enabled(as_of).exists())


def preliminary_vote_counts_enabled(as_of=None):
    """
    The preliminary vote count submitting period is the same as the polling
    reporting period.

    (This can be overridden by ENABLE_ALL_TOOLS.)
    """
    return polling_reports_enabled(as_of)


def polling_reports_enabled(as_of=None):
    """
    The polling reporting period is from the time polling starts until 16 hours
    after polling ends.
    """
    return (settings.ENABLE_ALL_TOOLS
            or Election.objects.get_elections_with_polling_reports_enabled(as_of).exists())


def is_blacklisted(number):
    """
    Return True if 'number' is on the blacklist.
    """
    blacklist = cache.get('blacklist')
    if blacklist is None:
        blacklist = set(Blacklist.objects.values_list('phone_number', flat=True))
        cache.set('blacklist', blacklist)
    return number in blacklist


def is_whitelisted(number):
    """
    Return True if 'number' is on the whitelist.
    """
    cache_key = 'whitelist:%s' % number
    whitelisted = cache.get(cache_key)
    if whitelisted is None:
        whitelisted = Whitelist.objects.filter(phone_number=number).exists()
        if whitelisted:
            # Only cache if number is on the whitelist
            cache.set(cache_key, whitelisted)
    return whitelisted


def remaining_registrations(number):
    """Return how many more registrations can be made using this phone"""
    num_already = Registration.objects.filter(sms__from_number=number).count()
    remaining = settings.MAX_REGISTRATIONS_PER_PHONE - num_already
    return max(0, remaining)


def is_center_id_valid(center_id):
    try:
        int_center_id = int(center_id)
        assert CENTER_ID_MIN_INT_VALUE <= int_center_id <= CENTER_ID_MAX_INT_VALUE
    except (AssertionError, TypeError, ValueError):
        return False
    return True


def import_center_csv_row(columns, row, line_number, stats, errors):
    """Import a CSV row and add, update, ignore, or raise an error as appropriate.

    This is a support function for update_center_table().
    """
    if any(row):
        if len(row) != len(CSV_FIELDS):
            errors.append(PARSING_ERROR.format(line_number=line_number, columns=columns))
            return

        # create a dictionary analogous to request.POST to feed to form
        data = dict(zip(CSV_FIELDS, row))
        try:
            # pull center_id and see if this center exists (so we know whether to update or insert)
            center = RegistrationCenter.objects.get(center_id=data['center_id'])
        except RegistrationCenter.DoesNotExist:
            center = None
        except ValueError:
            # bad center_id, but we'll validate it properly below
            center = None
        if center:
            # This is an update
            action = 'num_updated'
            # Set the initial values of our non-model form fields
            # so we can tell if they've changed later
            with override('ar'):
                old_center_type = force_text(center.get_center_type_display())
            # FK fields must be None so that the form doesn't consider them changed.
            initial = {
                'office_id': center.office.id,
                'office': None,
                'constituency_id': center.constituency.id,
                'constituency': None,
                'subconstituency_id': center.subconstituency.id,
                'subconstituency': None,
                'copy_of': None,
                'center_type': old_center_type
            }
            if center.copy_of:
                initial['copy_of_id'] = center.copy_of.center_id

            form = RegistrationCenterCSVForm(instance=center, initial=initial, data=data)
        else:
            # This is an insert
            action = 'num_created'
            form = RegistrationCenterCSVForm(data=data)
        if form.is_valid():
            if form.has_changed():
                logger.debug('The following fields on center have changed %s', form.changed_data)
                stats[action] += 1
                form.save()
            else:
                stats['num_dupes'] += 1
        else:
            for field_name, form_errors in form.errors.iteritems():
                for error in form_errors:
                    if field_name in data:
                        # this is a field-specific error
                        errors.append(FORM_FIELD_ERROR.format(line_number=line_number,
                                                              field_name=field_name,
                                                              value=data[field_name],
                                                              error=error))
                    else:
                        # this is non-field error
                        errors.append(FORM_ERROR.format(line_number=line_number, error=error))
    else:
        stats['num_blank'] += 1


class CenterImportFailedError(Exception):
    """Custom exception raised when CSV center import was not successful"""
    pass


def update_center_table(_file):
    """
    Import voting centers from a CSV file. It creates or updates.
    Safe to run repeatedly; if a voting center already exists with the
    center ID being imported it will update it if needed.

    Returns a 2-tuple of (message, successful), where message is status information (including
    errors, if any) and successful is a Boolean.

    If any errors are reported, no imports occur.
    """
    errors = []
    reader = UnicodeReader(_file)

    stats = {
        'num_blank': 0,
        'num_created': 0,
        'num_dupes': 0,
        'num_updated': 0,
    }

    line_number = 1
    columns = ", ".join(CSV_FIELDS)
    headers = reader.next()  # gets rid of the header row

    if not len(headers) == len(CSV_FIELDS):
        return PARSING_ERROR.format(line_number=1, columns=columns), False

    for index, header in enumerate(headers):
        if not header == CSV_FIELDS[index]:
            return PARSING_ERROR.format(line_number=1, columns=columns), False

    # If errors happen during the import and we want Django to roll
    # back the transaction, we need to exit the transaction context
    # with an exception (eventually).
    try:
        with transaction.atomic():
            for row in reader:
                line_number += 1
                import_center_csv_row(columns, row, line_number, stats, errors)

            if errors:
                errors.insert(0, force_text(ERRORS_OCCURRED_MESSAGE))
                message = mark_safe('<br><br>'.join(errors))
                logger.debug(errors)
                # trigger rollback:
                raise CenterImportFailedError
            else:
                message = STATUS_MESSAGE.format(blank=stats['num_blank'],
                                                created=stats['num_created'],
                                                dupes=stats['num_dupes'],
                                                updated=stats['num_updated'])
    except CenterImportFailedError:
        # Just to trigger a rollback
        logger.debug("Rolled back all imported centers due to errors.")
    else:
        logger.debug("No errors during import, will commit changes if nothing else goes wrong "
                     "during the request.")

    return message, not bool(errors)


def process_blackwhitelisted_numbers_file(model, import_file):
    """Process a text file with one phone number per line, adding each phone number to the model.

    The model must be one of Blacklist or Whitelist. The import_file must be an open file object.
    """
    imported = skipped = 0
    errors = []
    for line_number, line in enumerate(import_file.read().splitlines()):
        phone_number = canonicalize_phone_number(line)
        if phone_number:
            if model.objects.filter(phone_number=phone_number).exists():
                skipped += 1
            else:
                obj = model(phone_number=phone_number)
                try:
                    obj.full_clean()
                except ValidationError:
                    errors.append(str(line_number + 1))
                else:
                    obj.save()
                    imported += 1
    return (imported, skipped, errors)
