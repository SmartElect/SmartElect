# Python imports
import datetime
import logging

from django.conf import settings
from pytz import timezone

# Project imports
from register.models import Office
from .constants import COUNTRY, OFFICE, POLLING_CENTER_CODE, POLLING_CENTER_COPY_OF, \
    POLLING_CENTER_TYPE, REGION, SUBCONSTITUENCY_ID
from . import query

logger = logging.getLogger(__name__)


DEFAULT_DATE_TIME_COLUMNS = ('creation_date', )


def dictfetchall(cursor, date_time_columns=DEFAULT_DATE_TIME_COLUMNS):
    """Returns all rows from a cursor as a dict, and presents date/time columns
    according to settings.TIME_ZONE.

    The simple form, when we don't have to change the presentation of
    any dates or times, is from the Django documentation, at
    https://docs.djangoproject.com/en/1.6/topics/db/sql/
    """
    desc = cursor.description
    result_columns = set([col[0] for col in desc])
    if date_time_columns is None:
        date_time_columns = ()
    if result_columns.isdisjoint(set(date_time_columns)):
        return [
            dict(list(zip([col[0] for col in desc], row)))
            for row in cursor.fetchall()
        ]

    pres_tz = timezone(settings.TIME_ZONE)
    result = []
    warned = []
    for row in cursor.fetchall():
        values = []
        for i, col in enumerate(desc):
            if col[0] in date_time_columns:
                t = row[i]
                if isinstance(t, datetime.datetime):
                    t = t.astimezone(pres_tz)
                else:
                    if col[0] not in warned:
                        logging.warning('Column "%s" should be date/time but is %s' %
                                        (col[0], type(t)))
                        warned.append(col[0])
                values.append(t)
            else:
                values.append(row[i])
        result.append(dict(list(zip([col[0] for col in desc], values))))
    return result


def get_polling_centers(cursor, polling_locations):
    cursor.execute(query.CENTERS_AND_PHONES)
    polling_centers = {}

    # create polling center dict
    for (center_id, name, phones, reg_count) in cursor:
        d = {}
        d[POLLING_CENTER_CODE] = center_id
        d['name'] = name  # only available in native language
        d['phones'] = phones
        d['registration_count'] = reg_count
        try:
            (office_id, center_type, subconstituency_id, copy_of) = polling_locations[center_id]
            d[OFFICE] = office_id
            d[POLLING_CENTER_TYPE] = center_type
            if copy_of:
                d[POLLING_CENTER_COPY_OF] = copy_of
            d[SUBCONSTITUENCY_ID] = subconstituency_id
            region = Office.objects.get(id=office_id).region
            d[REGION] = Office.REGION_NAMES[region]
            d[COUNTRY] = 'Libya'
        except KeyError:
            # don't log missing invalid centers
            if center_id > 11000 and center_id not in [88888, 99999]:
                logger.error("Polling center missing from codings: %s" % center_id)
            continue
        except Office.DoesNotExist:
            logger.error("office_id missing from Office table: %s" % office_id)
            continue
        polling_centers[int(center_id)] = d

    return polling_centers


def get_datetime_from_local_date_and_time(date_str, time_str):
    """ Return TZ-aware datetime from a date string of form
                 %Y-%m-%d
        and time string of form
                 %H:%M:%S[.microseconds]
        The time zone for the input is (implicitly) settings.TZ.
    """
    together = '%s %s' % (date_str, time_str)
    # First, get a naive datetime
    dt = None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f'):
        try:
            dt = datetime.datetime.strptime(together, fmt)
        except ValueError:
            pass
    if not dt:
        raise ValueError('Could not parse "%s" with or without microseconds' % together)
    return timezone(settings.TIME_ZONE).localize(dt)
