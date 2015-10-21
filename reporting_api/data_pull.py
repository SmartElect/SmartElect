# Python imports
from collections import defaultdict
import datetime
import logging

# 3rd party imports
from django.conf import settings
from django.db import connection
from django.utils import translation

# Project imports
import codings
import query
from libya_elections.utils import ConnectionInTZ
from register.models import Office
from .aggregate import aggregate_up, aggregate_nested_key, aggregate_dates
from .constants import COUNTRY, MESSAGE_TYPE, OFFICE, POLLING_CENTER_CODE, \
    POLLING_CENTER_COPY_OF, POLLING_CENTER_TYPE, REGION, SUBCONSTITUENCY_ID
from .data_pull_common import get_offices, get_subconstituencies

logger = logging.getLogger(__name__)


def demo_dict_template():
    """Sets up a defaultdict template with age brackets, gender counts as [M,F], and total."""
    to_return = defaultdict(lambda: [0, 0])
    for age_range in set(codings.AGE_CODING.values()):
        to_return[age_range] = 0
    to_return['total'] = 0
    return to_return


def sms_msg_count_template():
    """Sets up a defaultdict template with incoming, outgoing, total """
    to_return = {}
    for direction in set(codings.MESSAGE_DIRECTION.values()):
        to_return[direction] = 0
    # to_return['failed'] = -1 #not sure where we'd get this data from, but it's in the mockup
    to_return['total'] = 0
    return to_return


def sms_datedict_template():
    """Dict with date keys, msg_count values """
    return defaultdict(lambda: sms_msg_count_template())


def get_polling_center_dicts(cursor, polling_locations):
    all_dates = set()
    polling_to_demo = defaultdict(lambda: demo_dict_template())

    # DEMO_QUERY converts a TIMESTAMP to a DATE, which must be
    # done in a TZ-aware manner so that the date reflects the
    # local time zone.
    with ConnectionInTZ(cursor, settings.TIME_ZONE):
        cursor.execute(query.DEMO_QUERY)

        # convert db codings to defaultdict structure
        for (date, gender, age, center_id, count) in cursor:
            polling_dict = polling_to_demo[center_id]
            polling_dict['total'] += count
            formatted_date = date.strftime('%Y-%m-%d')
            all_dates.add(formatted_date)
            if codings.GENDER_CODING[gender] == 'Male':
                polling_dict[formatted_date][0] += count
            else:
                polling_dict[formatted_date][1] += count
            try:
                polling_dict[codings.AGE_CODING[age]] += count
            except KeyError:
                logger.error("registration outside of codings.AGE_CODING, skip it (age %s)" % age)
                continue

    to_return = {}

    for (k, def_d) in polling_to_demo.iteritems():
        # Copy to regular dict (not defaultdict)
        d = dict(def_d)
        d[POLLING_CENTER_CODE] = k
        try:
            (office_id, center_type, subconstituency_id, copy_of) = polling_locations[k]
        except KeyError:
            logger.error("polling center missing from polling_locations: %s" % k)
            continue

        d[OFFICE] = office_id
        d[POLLING_CENTER_TYPE] = center_type
        if copy_of:
            d[POLLING_CENTER_COPY_OF] = copy_of
        d[SUBCONSTITUENCY_ID] = subconstituency_id

        try:
            region = Office.objects.get(id=office_id).region
            d[REGION] = Office.REGION_NAMES[region]
        except Office.DoesNotExist:
            logger.error("office_id missing from Office table: %s" % office_id)
            continue
        except KeyError:
            logger.error("region missing from Office.REGION_NAMES: %s" % region)
            logger.error(Office.REGION_NAMES)
            continue
        d[COUNTRY] = 'Libya'
        to_return[k] = d
    return to_return, all_dates


def get_sms_dicts(cursor):
    sms_messages = defaultdict(lambda: sms_datedict_template())

    # SMS message type strings are translatable but must be in English in the
    # report; disable translation to use the strings in the code.
    # (If message direction strings are ever translated, they will need the same
    # handling here.)
    with translation.override(language=None):
        # MESSAGES_QUERY converts a TIMESTAMP to a DATE, which must be
        # done in a TZ-aware manner so that the date reflects the
        # local time zone.
        with ConnectionInTZ(cursor, settings.TIME_ZONE):
            cursor.execute(query.MESSAGES_QUERY)
            for (date, direction, msg_type, count) in cursor:
                msg_type_dict = sms_messages[msg_type]

                formatted_date = date.strftime('%Y-%m-%d')
                msg_type_dict[formatted_date][codings.MESSAGE_DIRECTION[direction]] += count
                msg_type_dict[formatted_date]['total'] += count
                try:
                    # Message type strings are lazily translated; force the translation here
                    # since the JSON encoder won't otherwise resolve it.
                    msg_type_dict[MESSAGE_TYPE] = unicode(codings.MESSAGE_TYPES[msg_type])
                except KeyError:
                    msg_type_dict[MESSAGE_TYPE] = msg_type
    return sms_messages


def multiple_family_book_registrations(cursor):
    cursor.execute(query.PHONE_MULTIPLE_FAMILY_BOOK_QUERY)
    fbrn = {}
    for (from_number, num_count, num_list, latest) in cursor:
        fbrn[from_number] = num_list
    return fbrn


def duplicate_registrations(cursor):
    cursor.execute(query.DUPLICATE_REGISTRATIONS_QUERY)
    dups = defaultdict(list)
    for (to_number, date) in cursor:
        dups[to_number].append(date)
        # more info we might want to display here?
    return dict(dups)


def get_raw_data(polling_locations):
    """
    Get all the data we need from the database
    """
    cursor = connection.cursor()

    # POLLING CENTERS
    logger.info("running polling center query")
    polling_center_code_to_demo, all_dates = get_polling_center_dicts(cursor, polling_locations)

    # SMS
    logger.info("running messages query")
    sms_dict = get_sms_dicts(cursor)

    fbrn_dict = multiple_family_book_registrations(cursor)
    duplicate_dict = duplicate_registrations(cursor)
    return polling_center_code_to_demo, sms_dict, fbrn_dict, duplicate_dict, all_dates


def process_raw_data(polling_center_code_to_demo, sms_dict, fbrn_dict, duplicate_dict, all_dates):
    subconstituency_to_demo = aggregate_up(polling_center_code_to_demo.itervalues(),
                                           aggregate_key=SUBCONSTITUENCY_ID,
                                           lesser_key='polling_center',
                                           skip_keys=(POLLING_CENTER_CODE,
                                                      POLLING_CENTER_COPY_OF, POLLING_CENTER_TYPE),
                                           copy_keys=(OFFICE, REGION, COUNTRY, SUBCONSTITUENCY_ID))
    office_to_demo = aggregate_up(polling_center_code_to_demo.itervalues(),
                                  aggregate_key=OFFICE,
                                  lesser_key='polling_center',
                                  skip_keys=(SUBCONSTITUENCY_ID, POLLING_CENTER_CODE,
                                             POLLING_CENTER_COPY_OF, POLLING_CENTER_TYPE),
                                  copy_keys=(OFFICE, REGION, COUNTRY))
    region_to_demo = aggregate_up(office_to_demo.itervalues(),
                                  aggregate_key=REGION,
                                  lesser_key='office',
                                  skip_keys=(OFFICE, ),
                                  copy_keys=(REGION, COUNTRY))
    country_to_demo = aggregate_up(region_to_demo.itervalues(),
                                   aggregate_key=COUNTRY,
                                   lesser_key=REGION,
                                   skip_keys=(REGION, ),
                                   copy_keys=(COUNTRY,))

    message_stats = aggregate_nested_key(sms_dict, MESSAGE_TYPE, 'total')
    sms_stats = {'messages': aggregate_dates(aggregate_nested_key(sms_dict, MESSAGE_TYPE,
                                                                  'incoming'))}

    output_dict = {
        'subconstituencies': get_subconstituencies(),
        'offices': get_offices(),
        'by_' + COUNTRY: country_to_demo.values(),
        'by_' + REGION: region_to_demo.values(),
        'by_' + OFFICE: office_to_demo.values(),
        'by_' + SUBCONSTITUENCY_ID: subconstituency_to_demo.values(),
        'by_' + POLLING_CENTER_CODE: polling_center_code_to_demo.values(),
        'demographic_breakdowns': {
            'by_age': list(sorted(set(codings.AGE_CODING.values())))},
        'dates': list(sorted(all_dates)),
        'phone_multiple_family_book': len(fbrn_dict),
        'phone_duplicate_registrations': len(duplicate_dict),
        'sms_stats': sms_stats,
        'message_stats': message_stats,
        'last_updated': datetime.datetime.now().isoformat()}

    return output_dict


def pull_data(polling_locations):
    polling_center_code_to_demo, sms_dict, fbrn_dict, duplicate_dict, all_dates =\
        get_raw_data(polling_locations)
    return process_raw_data(polling_center_code_to_demo, sms_dict, fbrn_dict, duplicate_dict,
                            all_dates)
