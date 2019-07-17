# Python imports
from collections import defaultdict, Iterable
from copy import deepcopy
from datetime import datetime, timedelta
import json
import logging
import numbers

# 3rd party imports
import dateutil.parser
from django.conf import settings
from django.utils.timezone import now
from pytz import timezone
import redis

# Project imports
from libya_elections.utils import astz
from voting.models import Election
from .encoder import DateTimeEncoder
from . import data_pull_common
from . import data_pull
from . import data_pull_ed
from .models import ElectionReport
from .utils import get_datetime_from_local_date_and_time

logger = logging.getLogger(__name__)

report_store = redis.StrictRedis(**settings.REPORTING_REDIS_SETTINGS)
report_store_replica = redis.StrictRedis(**settings.REPORTING_REDIS_REPLICA_SETTINGS)

# Redis keys used for the various reports (prefixed by REPORTING_REDIS_KEY_PREFIX).
# If/when these key values changed, a migration step of removing the old keys from
# Redis may be required.
ELECTION_DAY_BY_COUNTRY_KEY = 'election_%d_by_country'
ELECTION_DAY_BY_OFFICE_KEY = 'election_%d_by_office'
ELECTION_DAY_LOG_KEY = 'election_%d_log'
ELECTION_DAY_METADATA_KEY = 'election_%d_metadata'
ELECTION_DAY_OFFICES_TABLE_KEY = 'election_%d_offices'
ELECTION_DAY_POLLING_CENTER_LOG_KEY_TEMPLATE = 'election_%d_log_polling_center_%d'
ELECTION_DAY_POLLING_CENTERS_TABLE_KEY = 'election_%d_polling_centers'
ELECTION_DAY_POLLING_CENTER_TABLE_KEY_TEMPLATE = 'election_%d_polling_center_%d'
ELECTION_DAY_REPORT_KEY = 'election_%d_report'
ELECTION_DAY_HQ_REPORTS_KEY = 'election_%d_hq_reports'

# _POINTS_: x, y points for plotting
# _CR_: Cumulative Registrations THROUGH each of a series of dates
# _NR_: New Registrations ON each of a series of dates
REGISTRATION_POINTS_CR_BY_COUNTRY_KEY = 'registration_points_cr_by_country'
REGISTRATION_POINTS_NR_BY_COUNTRY_KEY = 'registration_points_nr_by_country'
REGISTRATION_POINTS_CR_BY_OFFICE_KEY = 'registration_points_cr_by_office'
REGISTRATION_POINTS_NR_BY_OFFICE_KEY = 'registration_points_nr_by_office'
REGISTRATION_POINTS_CR_BY_REGION_KEY = 'registration_points_cr_by_region'
REGISTRATION_POINTS_NR_BY_REGION_KEY = 'registration_points_nr_by_region'
REGISTRATION_POINTS_CR_BY_SUBCONSTITUENCY_KEY = 'registration_points_cr_by_subconstituency'
REGISTRATION_POINTS_NR_BY_SUBCONSTITUENCY_KEY = 'registration_points_nr_by_subconstituency'

REGISTRATIONS_BY_COUNTRY_KEY = 'registrations_by_country'
REGISTRATIONS_BY_OFFICE_KEY = 'registrations_by_office'
REGISTRATIONS_BY_POLLING_CENTER_KEY = 'registrations_by_polling_center'
REGISTRATIONS_BY_REGION_KEY = 'registrations_by_region'
REGISTRATIONS_BY_SUBCONSTITUENCY_KEY = 'registrations_by_subconstituency'
REGISTRATIONS_BY_PHONE_KEY = 'registrations_by_phone'
REGISTRATIONS_CSV_COUNTRY_STATS_KEY = 'registrations_csv_by_country'
REGISTRATIONS_CSV_OFFICE_STATS_KEY = 'registrations_csv_by_office'
REGISTRATIONS_CSV_REGION_STATS_KEY = 'registrations_csv_by_region'
REGISTRATIONS_CSV_SUBCONSTITUENCY_STATS_KEY = 'registrations_csv_by_subconstituency'
REGISTRATIONS_DAILY_BY_OFFICE_KEY = 'registrations_daily_by_office'
REGISTRATIONS_DAILY_BY_SUBCONSTITUENCY_KEY = 'registrations_daily_by_subconstituency'
REGISTRATIONS_METADATA_KEY = 'registrations_metadata'
REGISTRATIONS_OFFICE_STATS_KEY = 'registrations_office_stats'
REGISTRATIONS_REGION_STATS_KEY = 'registrations_region_stats'
REGISTRATIONS_STATS_KEY = 'registrations_stats'
REGISTRATIONS_SUBCONSTITUENCY_STATS_KEY = 'registrations_subconstituencies_stats'

# common abbreviated date+time format for voter registration dashboard
DASHBOARD_SHORT_DATETIME_FMT = '%d/%m %H:%M'


def election_day_polling_center_table_key(election, center_id):
    return ELECTION_DAY_POLLING_CENTER_TABLE_KEY_TEMPLATE % (election.id, center_id)


def election_day_polling_center_log_key(election, center_id):
    return ELECTION_DAY_POLLING_CENTER_LOG_KEY_TEMPLATE % (election.id, center_id)


def redis_key(key):
    """ Take a raw key or list of raw keys and add the prefix. """
    if isinstance(key, str):
        return settings.REPORTING_REDIS_KEY_PREFIX + key
    else:
        return [settings.REPORTING_REDIS_KEY_PREFIX + k for k in key]


def election_key(key, election):
    return key % election.id


def empty_report_store():
    all_keys = report_store.keys(pattern=settings.REPORTING_REDIS_KEY_PREFIX + '*')
    if all_keys:
        logger.info('Removing %s from cache', all_keys)
        report_store.delete(*all_keys)


def retrieve_report(key):
    """
    Retrieve a report from Redis, returning None if it hasn't already been generated.
    (It won't be available until the report generation task populates Redis.) We use
    report_store_replica to retrieve the report from a local replica (if provided in
    settings) to save time.

    If a list of keys is provided, and any of them could not be found, the first result
    will be set to None for easier error checking, whether or not the corresponding key
    could be located.  (The assumption is that the caller will not continue if some of
    the requested data is missing.)  The Redis interface will of course set other results
    to None if the corresponding keys could not be located.

    If a single key has been provided (as a string) and it could not be found, None will
    be returned.
    """
    if isinstance(key, str):
        data_out = report_store_replica.get(redis_key(key))
        if data_out is not None:
            logger.debug('returning %s from cache', key)
            return json.loads(data_out.decode())
        else:
            logger.warning('%s not available in the cache and won\'t be generated', key)
            return None
    else:
        data_out = report_store_replica.mget(redis_key(key))
        if None in data_out:
            logger.warning('Keys %s not available in the cache and won\'t be generated',
                           [k for i, k in enumerate(key) if data_out[i] is None])
            # Make it easy for caller to check for failure -- 1st element always None on error
            data_out[0] = None
            return data_out
        return [json.loads(d.decode()) for d in data_out]


def parse_iso_datetime(s):
    """ Create a datetime from an ISO-like date/time string.  The strings generally
    have this format, but microseconds and time zone may be omitted:
      2014-08-18T17:35:31.043332+02:00
    """
    return dateutil.parser.parse(s)


def printable_iso_datetime(s):
    """ Create an abbreviated printable form from an ISO-like date/time string as
    accepted by parse_iso_datetime().
    """
    return parse_iso_datetime(s).strftime(DASHBOARD_SHORT_DATETIME_FMT)


def parse_date_and_time(date_str, time_str):
    """ Create a datetime from separate date and time strings of the following format:
      2014-08-18
      17:35:31.043332
    """
    return parse_iso_datetime(date_str + 'T' + time_str)


def printable_date_and_time(date_str, time_str):
    """ Create an abbreviated printable form from date and time strings of the following
    format:
      2014-08-18
      17:35:31.043332
    """
    return parse_date_and_time(date_str, time_str).strftime(DASHBOARD_SHORT_DATETIME_FMT)


def parse_dates(dates):
    """ Given a list of dates in string format ('YYYY-mm-dd'), return a
    corresponding list of Date objects.
    """
    return [datetime.strptime(a_date_string, '%Y-%m-%d').date() for a_date_string in dates]


def calc_yesterday(dates, dates_d=None):
    """ Given a list of date strings from a report, find "yesterday"
    and return it in datetime and string form.  Dates are always in order
    on input.  Return "yesterday" in both datetime.date and %Y-%m-%d format.

    "yesterday" is the most recent date with registrations.

    If the dates are already available as date objects, pass that in as dates_d.

    If there haven't been any registrations, dates will be empty; return
    None, None.
    """
    if not dates:
        return None, None

    if dates_d is None:
        # We only need to parse the last date for this function
        dates_d = parse_dates(dates[-1:])

    yesterday_date_str = dates[-1]
    yesterday_date = dates_d[-1]

    return yesterday_date, yesterday_date_str


def calc_by_grouping(groups, groups_key, dates, yesterday_date_str, age_groupings):
    """ Compute a general summary suitable for the primary groupings within
    the registration report. """
    logger.info('Calculating stats for grouping "%s"', groups_key)

    # template for data computed overall ('total') and for each element of groups
    group_template = {
        'm': 0,
        'f': 0,
        't': 0,
        'm_yesterday': 0,
        'f_yesterday': 0,
        't_yesterday': 0,
        # and zeros for each age group
    }
    for age in age_groupings:
        group_template[age] = 0

    total_stats = deepcopy(group_template)

    stats = dict()

    for group in groups:
        this_group = group[groups_key]
        males = females = 0
        males_yesterday = females_yesterday = 0
        for d in dates:
            if d in group:
                date_males, date_females = group[d]
            else:
                date_males, date_females = 0, 0
            males += date_males
            females += date_females
            if d == yesterday_date_str:
                males_yesterday = date_males
                females_yesterday = date_females
        by_age = []
        for age in age_groupings:
            by_age.append(group[age])

        group_stats = deepcopy(group_template)
        group_stats['id'] = group[groups_key]
        group_stats['m'] = males
        group_stats['f'] = females
        group_stats['t'] = males + females
        group_stats['m_yesterday'] = males_yesterday
        group_stats['f_yesterday'] = females_yesterday
        group_stats['t_yesterday'] = males_yesterday + females_yesterday
        for age in age_groupings:
            group_stats[age] = group[age]

        stats[this_group] = group_stats

        # update summary with data from this group
        total_stats['m'] += males
        total_stats['f'] += females
        total_stats['m_yesterday'] += males_yesterday
        total_stats['f_yesterday'] += females_yesterday
        for age in age_groupings:
            total_stats[age] += group[age]

    # add male and female overall
    total_stats['t'] = total_stats['m'] + total_stats['f']
    total_stats['t_yesterday'] = total_stats['m_yesterday'] + total_stats['f_yesterday']

    stats['total'] = total_stats
    return stats


def label(all_data, val, t):
    """ Return data to be used as the column label in a spreadsheet and
    denote whether or not the label must be translated, returning the
    tuple

        (label-data, should-label-be-translated?)

    On input:
    all_data -- registration report
    val -- the id we're looking for in a particular slice of all_data
    t -- indicates which slice of all_data we're looking at (e.g., by office,
      or by subconstituency)
    """
    if t == "subconstituency_id":
        for row in all_data['subconstituencies']:
            if row['code'] == val:
                return row, False
    elif t == "office_id":
        for row in all_data['offices']:
            if row['code'] == val:
                return row, False
    else:
        return val, True


def add_stats(all_data, yesterday_date_str, rows, key):
    """ Given the entire registration report, augment a particular slice
    of the data with male/female/total counts and label for each row.

    The input rows are dictionaries with entries containing male and
    female registrations by date, and total registrations by age group
    (as well as country, region, and a few other data points).

    On output, the row will gain:

    - label for spreadsheet row and whether or not to translate it
    - Male/Female/Total counts for total, yesterday, and penultimate day

    On input:
    all_data -- registration report
    yesterday_date_str -- "yesterday"
    rows -- a copy of a slice of all_data (e.g., by office, or by subconstituency),
            which will be augmented with counts and labels
    key -- the key in all_data which yields the desired slice
    """
    dates = all_data['dates']
    penultimate_day = dates[-2] if len(dates) >= 2 else None

    result = []
    for row in rows:
        row['label'], row['label_translated'] = label(all_data, row[key], key)

        m = sum([row.get(d, [0, 0])[0] for d in dates])
        f = sum([row.get(d, [0, 0])[1] for d in dates])
        row['total'] = [m + f, m, f]

        if dates[0] != dates[-1]:
            if yesterday_date_str in row:
                m = row[yesterday_date_str][0]
                f = row[yesterday_date_str][1]
                row['yesterday'] = [m + f, m, f]
            else:
                row['yesterday'] = [0, 0, 0]

            if penultimate_day in row:
                m = row[penultimate_day][0]
                f = row[penultimate_day][1]
                row['penultimate_day'] = [m + f, m, f]
            else:
                row['penultimate_day'] = [0, 0, 0]
        else:
            row['yesterday'] = row['penultimate_day'] = [0, 0, 0]

        result.append(row)

    return result


def yearweek_key(d):
    """ For the given date, return a key consisting of the year and the week of the year, where
    the weeks start on Sunday.
    """
    # move date forward by almost a week (simulates week starting on Sunday rather than Monday)
    d += timedelta(days=6)
    return d.strftime('%Y%U')


def add_sum_row(table, dates, dates_d, ages):
    """ Calculate a row consisting of the sums by column,
    and append it to the table.
    """

    # template for what gets added to the table
    totals = {'label': 'Total',
              'label_translated': True,
              'total': [0, 0, 0],
              'yesterday': [0, 0, 0],
              'class': 'sum-row',
              'days': {},
              'weeks': {}
              }

    for i, d in enumerate(dates):
        totals[d] = 0
        totals['days'][d] = [0, 0, 0]
        totals['weeks'][yearweek_key(dates_d[i])] = 0
        totals['cda'] = 0

    for age in ages:
        totals[age] = 0

    # each column stores data slightly differently
    # handle each data type separately
    for row in table:
        for key, col in row.items():
            if key in ['total', 'yesterday']:
                # add as t/m/f array
                totals[key][0] += col[0]
                totals[key][1] += col[1]
                totals[key][2] += col[2]
            elif key in dates:
                # add the total, not the m/f breakdown
                totals[key] += (col[0] + col[1])
            elif key in ages:
                # add int to total
                totals[key] += col
            elif key == 'cda':
                totals[key] += col
            elif key in ['days', 'weeks']:
                # add each period value in hash
                for period, val in col.items():
                    if period in totals[key]:
                        if isinstance(val, Iterable):
                            # days stored with t/m/f array
                            if not totals[key][period]:
                                totals[key][period] = [0, 0, 0]
                            else:
                                totals[key][period][0] += val[0]
                                totals[key][period][1] += val[1]
                                totals[key][period][2] += val[2]
                        elif isinstance(val, numbers.Number):
                            # weeks just a total
                            totals[key][period] += val
                    else:
                        # create it
                        totals[key][period] = val

    # set pct_female at the end, so we don't have to weight averages
    totals['pct_female'] = totals['total'][2] / totals['total'][0] \
        if totals['total'][0] else 0.0

    table.append(totals)


def group_names(groups, group_id):
    """
    Return English and Arabic names of group (either Office or Subconstituency) with matching id,
    or None if not found.
    """
    for g in groups:
        if g['code'] == group_id:
            return g['english_name'], g['arabic_name']


def calc_daily_by_group(name_of_id_field, data_by_group, groups, dates, dates_d):
    """
    Summarize registrations by group (either Office or Subconstituency) by day (in decreasing
    order) and by M/F, returning rows for the daily CSV-formatted report.
    """
    result = []

    # This value is overwritten when writing the CSV in the proper language context
    header = ['EN', 'AR']
    for d in reversed(dates_d):  # columns are in decreasing order by day
        d_str = d.strftime("%d/%m/%Y")
        header.append("%s (M)" % d_str)
        header.append("%s (F)" % d_str)

    result.append(header)

    for group in data_by_group:
        row = list(group_names(groups, group[name_of_id_field]))

        for d in reversed(dates):  # columns are in decreasing order by day
            m, f = group.get(d, [0, 0])
            row.append(m)
            row.append(f)

        result.append(row)

    return result


def registration_points(table, key, dates, cumulative=False):
    """ Build a nested list of plottable points for the registration charts.
    :param table: the main registrations table
    :param key: which "slice" of the data, such as by-country, by-office, etc.
    :param dates: list of dates, in order, on which registrations were received
    :param cumulative: do the plots give cumulative registrations as of a date or
           new registrations on a date?
    :return: List of dictionaries for each subdivision of a slice of the registration table.
             For by-country, there's only one country so there will be one dictionary.
             For other slices, such as by-region, there are multiple subdivisions so
             there will be multiple dictionaries returned.
             Each dictionary contains 'points' => list of date/count pairs, and
                                      'label' => string label or dictionary with different forms.
             When some slice other than by-country is requested, the by-country dictionary is
             also included.
    """
    rows = table['by_' + key]
    lines = []
    for row in rows:
        line = {
            'label': label(table, row[key], key)[0],
            'points': []
        }

        if cumulative:
            # no guarantee that each date will be represented in the row, so we can't just
            # sum the first n values to get the cumulative sum
            for i, d in enumerate(dates):
                values_so_far = [sum(row[dates[j]]) for j in range(0, i + 1) if dates[j] in row]
                line['points'].append([d, sum(values_so_far)])
        else:
            for d in dates:
                if d in row:
                    line['points'].append([d, sum(row[d])])
                else:
                    line['points'].append([d, None])
        lines.append(line)

    if key == "country":
        return lines
    else:
        # include by-country data too
        return registration_points(table, "country", dates, cumulative=cumulative) + lines


def generate_registrations_reports():
    """
    Generate raw registration report, as well as several sub-groupings and
    summaries, for use by vr-dashboard.  These are saved in Redis, not returned.
    """
    logger.info('starting registration reporting')
    polling_locations = data_pull_common.get_active_registration_locations()
    # pull data from vr database
    data_out = data_pull.pull_data(polling_locations)

    by_office = data_out['by_office_id']
    by_region = data_out['by_region']
    by_subconstituency = data_out['by_subconstituency_id']

    dates = data_out['dates']
    dates_d = parse_dates(dates)

    yesterday_date, yesterday_date_str = calc_yesterday(dates, dates_d)
    region_stats = calc_by_grouping(by_region, 'region', dates,
                                    yesterday_date_str,
                                    data_out['demographic_breakdowns']['by_age'])
    subconstituency_stats = calc_by_grouping(by_subconstituency, 'subconstituency_id',
                                             dates, yesterday_date_str,
                                             data_out['demographic_breakdowns']['by_age'])
    office_stats = calc_by_grouping(by_office, 'office_id', dates,
                                    yesterday_date_str,
                                    data_out['demographic_breakdowns']['by_age'])

    stored_stats = {key: data_out[key]
                    for key in ('sms_stats', 'phone_multiple_family_book',
                                'phone_duplicate_registrations', 'message_stats')}
    stored_stats['headline'] = {'males': region_stats['total']['m'],
                                'females': region_stats['total']['f']}

    csv_country_stats = add_stats(data_out, yesterday_date_str,
                                  deepcopy(data_out['by_country']), 'country')

    csv_region_stats = add_stats(data_out, yesterday_date_str,
                                 deepcopy(data_out['by_region']), 'region')
    add_sum_row(csv_region_stats, dates, dates_d, data_out['demographic_breakdowns']['by_age'])

    csv_office_stats = add_stats(data_out, yesterday_date_str,
                                 deepcopy(data_out['by_office_id']), 'office_id')
    add_sum_row(csv_office_stats, dates, dates_d, data_out['demographic_breakdowns']['by_age'])

    csv_subconstituency_stats = add_stats(data_out, yesterday_date_str,
                                          deepcopy(data_out['by_subconstituency_id']),
                                          'subconstituency_id')
    add_sum_row(csv_subconstituency_stats, dates, dates_d,
                data_out['demographic_breakdowns']['by_age'])

    daily_by_office = calc_daily_by_group(
        'office_id', by_office, data_out['offices'],
        dates, dates_d)
    daily_by_subconstituency = calc_daily_by_group(
        'subconstituency_id', by_subconstituency, data_out['subconstituencies'],
        dates, dates_d)

    by_country_cr_points = registration_points(data_out, "country", dates, cumulative=True)
    by_country_nr_points = registration_points(data_out, "country", dates)
    by_office_cr_points = registration_points(data_out, "office_id", dates, cumulative=True)
    by_office_nr_points = registration_points(data_out, "office_id", dates)
    by_region_cr_points = registration_points(data_out, "region", dates, cumulative=True)
    by_region_nr_points = registration_points(data_out, "region", dates)
    by_subconstituency_cr_points = registration_points(data_out, "subconstituency_id", dates,
                                                       cumulative=True)
    by_subconstituency_nr_points = registration_points(data_out, "subconstituency_id", dates)

    logging.info('Pipe-lining the registrations-related report stores')
    # store in pieces for use by different dashboard displays, but in a
    # pipeline
    pipe = report_store.pipeline(transaction=False)
    metadata = {key: data_out[key]
                for key in ('demographic_breakdowns', 'subconstituencies',
                            'offices', 'last_updated', 'dates')}
    pipe.set(redis_key(REGISTRATIONS_METADATA_KEY),
             json.dumps(metadata, cls=DateTimeEncoder))
    pipe.set(redis_key(REGISTRATIONS_STATS_KEY),
             json.dumps(stored_stats))
    pipe.set(redis_key(REGISTRATIONS_OFFICE_STATS_KEY),
             json.dumps(office_stats))
    pipe.set(redis_key(REGISTRATIONS_CSV_COUNTRY_STATS_KEY),
             json.dumps(csv_country_stats))
    pipe.set(redis_key(REGISTRATIONS_CSV_OFFICE_STATS_KEY),
             json.dumps(csv_office_stats))
    pipe.set(redis_key(REGISTRATIONS_CSV_REGION_STATS_KEY),
             json.dumps(csv_region_stats))
    pipe.set(redis_key(REGISTRATIONS_CSV_SUBCONSTITUENCY_STATS_KEY),
             json.dumps(csv_subconstituency_stats))
    pipe.set(redis_key(REGISTRATIONS_REGION_STATS_KEY),
             json.dumps(region_stats))
    pipe.set(redis_key(REGISTRATIONS_SUBCONSTITUENCY_STATS_KEY),
             json.dumps(subconstituency_stats))
    pipe.set(redis_key(REGISTRATIONS_BY_SUBCONSTITUENCY_KEY),
             json.dumps(by_subconstituency))
    pipe.set(redis_key(REGISTRATIONS_BY_REGION_KEY),
             json.dumps(by_region))
    pipe.set(redis_key(REGISTRATIONS_BY_POLLING_CENTER_KEY),
             json.dumps(data_out['by_polling_center_code']))
    pipe.set(redis_key(REGISTRATIONS_DAILY_BY_OFFICE_KEY),
             json.dumps(daily_by_office))
    pipe.set(redis_key(REGISTRATIONS_DAILY_BY_SUBCONSTITUENCY_KEY),
             json.dumps(daily_by_subconstituency))
    pipe.set(redis_key(REGISTRATIONS_BY_OFFICE_KEY),
             json.dumps(by_office))
    pipe.set(redis_key(REGISTRATIONS_BY_COUNTRY_KEY),
             json.dumps(data_out['by_country']))
    pipe.set(redis_key(REGISTRATIONS_BY_PHONE_KEY),
             json.dumps(data_out['registrations_by_phone']))
    pipe.set(redis_key(REGISTRATION_POINTS_CR_BY_COUNTRY_KEY),
             json.dumps(by_country_cr_points))
    pipe.set(redis_key(REGISTRATION_POINTS_NR_BY_COUNTRY_KEY),
             json.dumps(by_country_nr_points))
    pipe.set(redis_key(REGISTRATION_POINTS_CR_BY_OFFICE_KEY),
             json.dumps(by_office_cr_points))
    pipe.set(redis_key(REGISTRATION_POINTS_NR_BY_OFFICE_KEY),
             json.dumps(by_office_nr_points))
    pipe.set(redis_key(REGISTRATION_POINTS_CR_BY_REGION_KEY),
             json.dumps(by_region_cr_points))
    pipe.set(redis_key(REGISTRATION_POINTS_NR_BY_REGION_KEY),
             json.dumps(by_region_nr_points))
    pipe.set(redis_key(REGISTRATION_POINTS_CR_BY_SUBCONSTITUENCY_KEY),
             json.dumps(by_subconstituency_cr_points))
    pipe.set(redis_key(REGISTRATION_POINTS_NR_BY_SUBCONSTITUENCY_KEY),
             json.dumps(by_subconstituency_nr_points))
    pipe.execute()


def generate_offices_table(offices, by_office, by_polling_center,
                           election_day, day_after_election_day):
    """ Pre-compute key data needed for generating election day
     office reports.
    """
    offices_by_key = {str(office['code']): office for office in offices}
    rows = []

    for key in sorted([key for key in by_office.keys()]):
        row = by_office[key]
        key = str(key)

        # copy name from the offices hash array
        row['english_name'] = offices_by_key[key]['english_name']
        row['arabic_name'] = offices_by_key[key]['arabic_name']
        on_election_day = row.get(election_day, {})

        # get election day numbers
        row['opened'] = on_election_day.get('opened', 0)
        row['votes_reported_1'] = on_election_day.get('1', 0)
        row['votes_reported_2'] = on_election_day.get('2', 0)
        row['votes_reported_3'] = on_election_day.get('3', 0)

        # and aggregate counts
        row['reported_1'] = on_election_day.get('1_count', 0)
        row['reported_2'] = on_election_day.get('2_count', 0)
        row['reported_3'] = on_election_day.get('3_count', 0)

        # check for late results
        # We only want late reports for period 4. The JSON data has aggregate
        # numbers for office by day, but you can't tell which of those values are new reports on
        # EDAY+1 and which ones are replacements for values given on EDAY, so we have to iterate
        # through each center to get that info
        row['votes_reported_4'] = 0
        reported_4 = 0
        # Which polling centers are in this office?
        centers = {k: v for k, v in by_polling_center.items() if str(v['office_id']) == key}
        for center_id, center in centers.items():
            if day_after_election_day in center and '4' in center[day_after_election_day]:
                # found a period 4 report on EDAY+1. Sum the votes and increment the report count
                row['votes_reported_4'] += center[day_after_election_day]['4']
                reported_4 += 1
            elif election_day in center and '4' in center[election_day]:
                # didn't find an EDAY+1 report, so use EDAY, if present
                row['votes_reported_4'] += center[election_day]['4']
                reported_4 += 1

        row['reported_4'] = reported_4
        # save derived values
        row['not_opened'] = row['polling_center_count'] - row['opened']
        row['not_reported_1'] = row['polling_center_count'] - row['reported_1']
        row['not_reported_2'] = row['polling_center_count'] - row['reported_2']
        row['not_reported_3'] = row['polling_center_count'] - row['reported_3']
        row['not_reported_4'] = row['polling_center_count'] - reported_4
        row['closed'] = reported_4  # reporting final tally means center closed

        rows.append(row)

    return rows


def get_effective_reminder_time():
    """ Isolate this particular use of now() so that the effective reminder time is
    practical to patch within tests.
    """
    return now()


def update_polling_centers_table(all_dates, all_centers, election, election_day_dt, election_day,
                                 day_after_election_day):
    """ Amend the "by_polling_center" slice of the election day report with additional
    data used to generate the election day views.
    """
    current_time = get_effective_reminder_time()
    reminder_strings = ['11:30', '15:30', '19:45', '21:30']
    reminders = [election_day_dt.replace(hour=int(s[0:2]), minute=int(s[3:5]))
                 for s in reminder_strings]
    period_keys = ['1', '2', '3', '4']

    for center_id, center in all_centers.items():
        center['closed'] = ('has_not_reported', 'No')

        # find most recent open, report time
        dates_opened = sorted([d for d in all_dates if d in center and 'opened' in center[d]])
        dates_reported = sorted([d for d in all_dates if d in center and 'reported' in center[d]])

        if dates_opened:
            # Validate that the open time is not too early.  A CenterOpen "should" be
            # created only inside the boundaries of an Election, but there may be some
            # historical data which is outside of the currently-allowable range.
            # (Additionally, the end-to-end dashboard test validates this behavior.)
            #
            # What about open times which are too late?  TBD
            this_open_time = get_datetime_from_local_date_and_time(
                dates_opened[-1],
                center[dates_opened[-1]]['opened']
            )
            if this_open_time < election.start_time:
                logger.error('Center %s has open time %s prior to election start time %s',
                             center_id, this_open_time, election.start_time)
            else:
                center['last_opened'] = printable_date_and_time(dates_opened[-1],
                                                                center[dates_opened[-1]]['opened'])

        if dates_reported:
            center['last_reported'] = \
                printable_date_and_time(dates_reported[-1],
                                        center[dates_reported[-1]]['reported'])

        # check if center has data for election day
        if election_day in center:
            on_election_day = center[election_day]
            if 'opened' in on_election_day:
                # drop seconds and microseconds
                center['opened'] = on_election_day['opened'] = \
                    on_election_day['opened'][:5]
                center['opened_today'] = on_election_day['opened_today'] = \
                    election_day_dt.strftime("%d/%m") + ' ' + on_election_day['opened']

            for i, period in enumerate(period_keys):
                if period in center[election_day]:
                    center['reported_period_' + period] = 'has_reported'
                    center['votes_reported_' + period] = on_election_day[period]
                elif current_time <= reminders[i]:
                    # reminder hasn't been sent yet
                    center['reported_period_' + period] = 'not_due'
                else:
                    center['reported_period_' + period] = 'has_not_reported'

            if '4' in on_election_day:
                center['closed'] = ('has_reported', 'Yes')

            if day_after_election_day in center:
                after_election_day = center[day_after_election_day]
                if '4' in after_election_day:
                    center['votes_reported_4'] = after_election_day['4']
                    center['reported_period_4'] = 'has_reported'
                    center['closed'] = ('has_reported', 'Yes')
        else:
            for period in period_keys:
                center['reported_period_' + period] = 'no_data'
            center['opened_today'] = None  # just for easy comparison with old Ruby implementation

        if day_after_election_day in center:
            if '4' in center[day_after_election_day]:
                center['votes_reported_4'] = center[day_after_election_day]['4']


def generate_centers_by_office(offices, by_polling_center):
    """ Generate table which provides a list of polling centers for each office.
    """
    table = defaultdict(list)
    for office in offices:
        office_id = office['code']
        centers = [by_polling_center[center_id]['polling_center_code']
                   for center_id in sorted(by_polling_center.keys())
                   if by_polling_center[center_id]['office_id'] == office_id]
        table[office_id] = sorted(centers)
    return table


def load_election_day_report(election, data_out):
    election_day_dt = election.polling_start_time
    election_day_dt = astz(election_day_dt, timezone(settings.TIME_ZONE))
    election_day = election_day_dt.strftime('%Y-%m-%d')

    day_after_election_day_dt = election_day_dt + timedelta(days=1)
    day_after_election_day = day_after_election_day_dt.strftime('%Y-%m-%d')

    polling_centers_by_office = generate_centers_by_office(data_out['offices'],
                                                           data_out['by_polling_center'])

    metadata = {
        'offices': data_out['offices'],
        'centers_by_office': polling_centers_by_office,
        'election_day': election_day,
        'dates': data_out['dates'],
        'last_updated': data_out['last_updated']
    }
    offices_table = generate_offices_table(data_out['offices'], deepcopy(data_out['by_office']),
                                           data_out['by_polling_center'],
                                           election_day, day_after_election_day)
    polling_centers_table = deepcopy(data_out['by_polling_center'])
    update_polling_centers_table(data_out['dates'], polling_centers_table, election,
                                 election_day_dt, election_day, day_after_election_day)

    centers = [polling_centers_table[key] for key in sorted(polling_centers_table.keys())]
    pipe = report_store.pipeline(transaction=False)
    pipe.set(redis_key(election_key(ELECTION_DAY_REPORT_KEY, election)), json.dumps(data_out))
    pipe.set(redis_key(election_key(ELECTION_DAY_BY_COUNTRY_KEY, election)),
             json.dumps(data_out['by_country']))
    pipe.set(redis_key(election_key(ELECTION_DAY_BY_OFFICE_KEY, election)),
             json.dumps(data_out['by_office']))
    pipe.set(redis_key(election_key(ELECTION_DAY_OFFICES_TABLE_KEY, election)),
             json.dumps(offices_table))
    pipe.set(redis_key(election_key(ELECTION_DAY_POLLING_CENTERS_TABLE_KEY, election)),
             json.dumps(centers))
    for center in centers:
        pipe.set(redis_key(election_day_polling_center_table_key(
            election, center['polling_center_code'])),
            json.dumps(center))
    pipe.set(redis_key(election_key(ELECTION_DAY_METADATA_KEY, election)),
             json.dumps(metadata, cls=DateTimeEncoder))
    pipe.execute()


def generate_and_load_election_day_report(election):
    """
    Generates raw election-day report in Python dict form, for use by vr-dashboard.
    These are saved in Redis and returned.
    """
    logger.info('starting election day reporting for election %s', election)
    # Centers ("locations") which aren't active for this election
    # will be represented in the report, though any vote reports from
    # them will be ignored.
    polling_locations = data_pull_common.get_all_polling_locations()
    data_out = data_pull_ed.pull_data(polling_locations, election)
    # Pre-computing data based on the election day report needs to work the same
    # whether we just created the report or we loaded an old one (in JSON format)
    # from the database.  Pull the new dictionary through JSON to convert any
    # int keys to strings and otherwise ensure that load_election_day_report()
    # also handles an old report from the db.
    data_out = json.loads(json.dumps(data_out))
    load_election_day_report(election, data_out)
    return data_out


def load_election_day_hq_reports(election, hq_reports):
    report_store.set(redis_key(election_key(ELECTION_DAY_HQ_REPORTS_KEY, election)),
                     json.dumps(hq_reports))


def generate_and_load_election_day_hq_reports(election):
    hq_reports = data_pull_ed.generate_election_day_hq_reports(election)
    load_election_day_hq_reports(election, hq_reports)
    return hq_reports


def load_election_day_log(election, data_out):
    pipe = report_store.pipeline(transaction=False)
    pipe.set(redis_key(election_key(ELECTION_DAY_LOG_KEY, election)),
             json.dumps(data_out, cls=DateTimeEncoder))
    for center_id in data_out.keys():
        pipe.set(redis_key(election_day_polling_center_log_key(election, int(center_id))),
                 json.dumps(data_out[center_id], cls=DateTimeEncoder))
    pipe.execute()


def generate_and_load_election_day_log(election):
    """
    Generates raw election-day log in Python dict form, for use by vr-dashboard.
    These are saved in Redis and returned.
    """
    logger.info('generating election day log for election %s', election)
    data_out = data_pull_ed.message_log(election)
    load_election_day_log(election, data_out)
    return data_out


def get_election_data_from_db(election):
    """
    :param election: An Election, represented in ElectionReport, for which the data
     should be returned.
    :return: tuple of report and message log
    """
    election_report = ElectionReport.objects.get(election=election)
    return (
        json.loads(election_report.report),
        json.loads(election_report.hq_reports),
        json.loads(election_report.message_log),
    )


def load_election_data(election):
    """
    :param election: An Election, represented in ElectionReport, for which the data
     needs to be loaded from db into Redis.
    :return: nothing
    """
    report, hq_reports, log = get_election_data_from_db(election)
    load_election_day_report(election, report)
    load_election_day_hq_reports(election, hq_reports)
    load_election_day_log(election, log)


def generate_election_day_reports_and_logs(rebuild_all=False):
    """
    :param rebuild_all: Rebuild reports even for old elections for which a report
    is in the database.
    """
    for election in Election.objects.all():
        # See if data for this election has been saved already.  If it has, and data
        # for the election is not still changing, then we just have to ensure that it
        # has been loaded into Redis since the last flush of Redis.
        existing = ElectionReport.objects.filter(election=election)
        if existing.count() == 1:  # already saved
            if not rebuild_all:  # okay to use existing report for old election
                if election.work_end_time < now():  # data not still changing
                    if not report_store.get(election_key(ELECTION_DAY_METADATA_KEY, election)):
                        load_election_data(election)
                    continue
        log = generate_and_load_election_day_log(election)
        report = generate_and_load_election_day_report(election)
        hq_reports = generate_and_load_election_day_hq_reports(election)
        if existing.count() == 1:
            record = existing[0]
        else:
            record = ElectionReport(election=election)

        record.message_log = json.dumps(log, cls=DateTimeEncoder)
        record.report = json.dumps(report)
        record.hq_reports = json.dumps(hq_reports)
        record.full_clean()
        record.save()
