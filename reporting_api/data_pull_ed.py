# Python imports
from collections import defaultdict, OrderedDict
import datetime
import logging

# 3rd party imports
from django.conf import settings
from django.db import connection
from django.db.models import Count

# Project imports
from libya_elections.utils import ConnectionInTZ
from polling_reports.models import CenterClosedForElection, PollingReport, PreliminaryVoteCount
from register.models import Office, RegistrationCenter
from .aggregate import aggregate_up, join_by_date, join_by_date_nested
from .constants import COUNTRY, INACTIVE_FOR_ELECTION, OFFICE, POLLING_CENTER_CODE, \
    POLLING_CENTER_COPY_OF, POLLING_CENTER_TYPE, PRELIMINARY_VOTE_COUNTS, REGION, \
    SUBCONSTITUENCY_ID
from .data_pull_common import get_offices
from .utils import dictfetchall, get_polling_centers
from . import query

logger = logging.getLogger(__name__)


def get_raw_data(polling_locations, election):
    """
    Get all the data we need from the database.
    """
    cursor = connection.cursor()
    logger.info("running ed queries")
    polling_centers = get_polling_centers(cursor, polling_locations)

    inactive_for_election = [
        inactive.registration_center.center_id
        for inactive in CenterClosedForElection.objects.filter(election=election)
    ]

    # The CENTER_OPENS and CENTER_VOTESREPORT queries split TIMESTAMPS into
    # separate date and time fields within the query.  Our custom dictfetchall()
    # can't currently adjust for time zone by accounting for separate fields.
    # Work around that by letting PostgreSQL adjust the TZ before splitting
    # the TIMESTAMP.  (A good alternative fix is not to complicate dictfetchall()
    # but instead to preserve the combined TIMESTAMP/datetime further once all
    # users of the data are in the integrated Django app.)
    with ConnectionInTZ(cursor, settings.TIME_ZONE):
        cursor.execute(query.CENTER_OPENS, {
            'ELECTION_ID': election.id,
        })
        # disable TZ adjustment in dictfetchall()
        center_opens = dictfetchall(cursor, date_time_columns=())
        cursor.execute(query.CENTER_VOTESREPORT, {
            'ELECTION_ID': election.id,
        })
        center_reports = dictfetchall(cursor, date_time_columns=())

    prelim_vote_counts = PreliminaryVoteCount.objects.filter(election=election)

    # The input will contain each key once per option, but it is okay
    # to keep only the last instance since the fields set initially
    # are the same.
    prelim_vote_counts_by_center = {
        str(prelim.registration_center.center_id): {
            COUNTRY: 'Libya',
            REGION: prelim.registration_center.office.region,
            OFFICE: prelim.registration_center.office_id,
            POLLING_CENTER_CODE: prelim.registration_center.center_id,
            PRELIMINARY_VOTE_COUNTS: dict()
        }
        for prelim in prelim_vote_counts
    }
    for prelim in prelim_vote_counts:
        this_polling_center_dict = \
            prelim_vote_counts_by_center[str(prelim.registration_center.center_id)]
        this_polling_center_dict[PRELIMINARY_VOTE_COUNTS][prelim.option] = prelim.num_votes

    logger.info("ed queries done")
    return polling_centers, inactive_for_election, center_opens, center_reports, \
        prelim_vote_counts_by_center


def summarize_opens_with_missing_center(missing):
    """ Log information about center open entries with an invalid
    center id.  As the query filters out invalid centers, this is
    unexpected, so don't assume much about the data.
    """
    for center_id in sorted(missing.keys()):
        logger.error('Invalid center %d referenced in %d roll call(s):' %
                     (center_id, len(missing[center_id])))
        for entry in missing[center_id]:
            logger.error('  Raw data: %s' % str(entry))


def summarize_reports_with_missing_center(missing):
    """ Log information about daily report entries with an invalid
    center id.
    """
    for center_id in sorted(missing.keys()):
        data = missing[center_id]
        data = sorted(data, key=lambda e: e['date'])
        last_date = data[-1]['date']
        total_reported = sum([entry['votes_reported'] for entry in data])
        logger.error('Invalid center %d in %d daily report(s); '
                     'latest report on %s, total votes %d' %
                     (center_id, len(data), last_date, total_reported))
        logger.debug(data)


def process_raw_data(polling_centers, inactive_for_election, center_opens, center_reports,
                     center_vote_counts):
    all_dates = set()

    logger.info("joining center opens")
    missing_centers = defaultdict(list)
    polling_centers = join_by_date(center_opens,
                                   'polling_center_code', 'date',
                                   ['opened'],
                                   polling_centers, all_dates, missing_centers)
    if missing_centers:
        # This shouldn't happen, as the query for CenterOpen already filters out
        # cases where the registration center is missing or soft-deleted, and an
        # CenterOpen is always related to a RegistrationCenter.
        summarize_opens_with_missing_center(missing_centers)

    logger.info("joining center reports")
    missing_centers = defaultdict(list)
    polling_centers = join_by_date_nested(center_reports,
                                          'polling_center_code', 'date',
                                          {'voting_period': 'votes_reported'},
                                          polling_centers, all_dates, missing_centers)
    if missing_centers:
        # A DailyReport is not tied to a RegistrationCenter in the database.  The
        # RegistrationCenter may be present but soft-deleted or not present at all.
        summarize_reports_with_missing_center(missing_centers)

    for inactive_center in inactive_for_election:
        polling_centers[inactive_center][INACTIVE_FOR_ELECTION] = True

    offices = aggregate_up(polling_centers.values(),
                           aggregate_key=OFFICE,
                           lesser_key='polling_center',
                           skip_keys=(SUBCONSTITUENCY_ID, POLLING_CENTER_CODE,
                                      POLLING_CENTER_COPY_OF, POLLING_CENTER_TYPE, 'phones'),
                           copy_keys=(OFFICE, REGION, COUNTRY),
                           enumerate_keys=((INACTIVE_FOR_ELECTION, POLLING_CENTER_CODE),),
                           # voting periods stored at X_count:
                           count_inner_keys=(1, 2, 3, 4, 'opened'),
                           sum_inner_keys=(1, 2, 3, 4))

    regions = aggregate_up(offices.values(),
                           aggregate_key=REGION,
                           lesser_key='office',
                           skip_keys=(OFFICE, 'name', INACTIVE_FOR_ELECTION),
                           copy_keys=(REGION, COUNTRY),
                           sum_inner_keys=(1, 2, 3, 4,
                                           '1_count', '2_count', '3_count', '4_count'))

    country = aggregate_up(regions.values(),
                           aggregate_key=COUNTRY,
                           lesser_key=REGION,
                           skip_keys=(REGION, 'name'),
                           copy_keys=(COUNTRY,),
                           sum_inner_keys=(1, 2, 3, 4,
                                           '1_count', '2_count', '3_count', '4_count'))

    # Office and broader groupings should include preliminary vote counts from centers
    # (and aggregate_up can't handle this)
    for center_dict in center_vote_counts.values():
        # office, region, and country representations must already exist by virtue of
        # the center being represented
        office_dict = offices[center_dict[OFFICE]]
        region_dict = regions[Office.REGION_NAMES[center_dict[REGION]]]
        country_dict = country[center_dict[COUNTRY]]

        for group_dict in (office_dict, region_dict, country_dict):
            if PRELIMINARY_VOTE_COUNTS not in group_dict:
                group_dict[PRELIMINARY_VOTE_COUNTS] = defaultdict(int)
            for vote_option in center_dict[PRELIMINARY_VOTE_COUNTS].keys():
                group_dict[PRELIMINARY_VOTE_COUNTS][vote_option] += \
                    center_dict[PRELIMINARY_VOTE_COUNTS][vote_option]

    output_dict = {
        'by_country': country,
        'by_region': regions,
        'by_office': offices,
        'by_polling_center': polling_centers,
        'offices': get_offices(),
        'dates': list(sorted(all_dates)),
        'last_updated': datetime.datetime.now().isoformat()}

    return output_dict


def pull_data(polling_locations, election):
    polling_centers, inactive_for_election, center_opens, center_reports, center_vote_counts = \
        get_raw_data(polling_locations, election)
    return process_raw_data(polling_centers, inactive_for_election, center_opens, center_reports,
                            center_vote_counts)


def message_log(election):
    logger.info("running message log queries")

    cursor = connection.cursor()

    cursor.execute(query.LOG_PHONES, {'NO_LATER_THAN': election.work_end_time})
    log_phones = dictfetchall(cursor)

    cursor.execute(query.LOG_ROLLCALL, {'ELECTION_ID': election.id})
    log_rollcall = dictfetchall(cursor)

    cursor.execute(query.LOG_VOTESREPORT, {'ELECTION_ID': election.id})
    log_report = dictfetchall(cursor)
    logger.info("message log queries done")

    logger.info("joining message logs")
    merged = []
    merged.extend(log_phones)
    merged.extend(log_rollcall)
    merged.extend(log_report)

    output = defaultdict(list)
    for item in merged:
        center_code = item['center_code']
        output[center_code].append(item)

    return output


def generate_election_day_hq_reports(election):
    """Generate election day HQ reports for the election day HQ view"""
    # Ignore centers which are inactive for polling for this election,
    # except when building the list of all centers.
    inactive_center_db_ids = [
        inactivity.registration_center.id
        for inactivity in CenterClosedForElection.objects.filter(election=election)
    ]
    # For a given center there are usually 4 polling reports, one for each reporting period.
    # Sometimes a center has multiple reports per period, and occasionally no report for a
    # period. Since PollingReports are cumulative, we only want the most recent report for each
    # center, and that's what this query does.
    # The use of .distinct('registration_center__id') at the end activates a Postgres-specific
    # 'DISTINCT ON' clause. See the queryset API ref for distinct, also see here:
    # http://stackoverflow.com/questions/3800551/select-first-row-in-each-group-by-group
    polling_reports = PollingReport.objects.filter(election=election,
                                                   registration_center__deleted=False) \
        .exclude(registration_center__id__in=inactive_center_db_ids) \
        .order_by('registration_center__id', '-period_number', '-modification_date') \
        .distinct('registration_center__id')

    open_centers = RegistrationCenter.objects.filter(centeropen__isnull=False) \
        .exclude(id__in=inactive_center_db_ids) \
        .distinct()

    all_centers = RegistrationCenter.objects.all() \
        .annotate(n_registrations=Count('registration')) \
        .order_by('center_id')

    # OK, all the queries are done. The next step is to loop through the results and count.

    all_offices = sorted(set([center.office for center in all_centers]))

    REPORT_TYPES = ('by_office', 'by_region', 'by_center_type', )

    # You can picture this dict of dicts as a tree. The root dict has children that are the
    # report types (plus national, which behaves a bit differently), the grandchildren are
    # all offices, all regions, and all center types, and the g-grandchildren are the leaf nodes,
    # or very nearly so. They're either 'v' (for vote count) which is a leaf node, or 'r' (for
    # registration count) which has leaf nodes 'open' and 'active'.
    d = {}

    for report_type in REPORT_TYPES:
        # Using an ordered dict here means that downstream consumers (like the template) get
        # results that are already sorted.
        d[report_type] = OrderedDict()
        if report_type == 'by_office':
            for office in all_offices:
                d[report_type][str(office.id)] = {'v': 0, 'r': {'open': 0, 'active': 0, }}
        elif report_type == 'by_region':
            for region in Office.ALL_REGIONS:
                d[report_type][str(region)] = {'v': 0, 'r': {'open': 0, 'active': 0, }}
        elif report_type == 'by_center_type':
            for center_type in RegistrationCenter.Types.ALL:
                d[report_type][str(center_type)] = {'v': 0, 'r': {'open': 0, 'active': 0, }}

    d['national'] = {}
    d['national']['r'] = {}
    d['national']['r']['open'] = 0
    d['national']['r']['active'] = 0
    d['national']['v'] = 0

    # Tally registrations
    for center in all_centers:
        is_open = center in open_centers

        for report_type in REPORT_TYPES:
            if report_type == 'by_office':
                key = str(center.office.id)
            elif report_type == 'by_region':
                key = str(center.office.region)
            elif report_type == 'by_center_type':
                key = str(center.center_type)

            d[report_type][key]['r']['active'] += center.n_registrations
            if report_type == 'by_region':
                d['national']['r']['active'] += center.n_registrations
            if is_open:
                d[report_type][key]['r']['open'] += center.n_registrations
                if report_type == 'by_region':
                    d['national']['r']['open'] += center.n_registrations

    all_centers = {center.id: center for center in all_centers}

    # Tally votes
    for polling_report in polling_reports:
        center = all_centers[polling_report.registration_center_id]

        for report_type in REPORT_TYPES:
            if report_type == 'by_office':
                key = str(center.office.id)
            elif report_type == 'by_region':
                key = str(center.office.region)
            elif report_type == 'by_center_type':
                if center.center_type == RegistrationCenter.Types.COPY:
                    # Copy center stats are rolled into the original center's stats in this context.
                    # See:
                    # https://github.com/hnec-vr/libya-elections/issues/1008#issuecomment-70111548
                    key = str(center.copy_of.center_type)
                else:
                    key = str(center.center_type)

            d[report_type][key]['v'] += polling_report.num_voters

    # Now that copy center stats have been counted and rolled into other categories, I delete them
    # so that they don't clutter up the report.
    del d['by_center_type'][str(RegistrationCenter.Types.COPY)]

    d['national']['r']['open'] = 0
    d['national']['r']['active'] = 0
    d['national']['v'] = 0

    d['national']['r']['open'] = sum([d['by_region'][str(region)]['r']['open'] for region in
                                     Office.ALL_REGIONS])
    d['national']['r']['active'] = sum([d['by_region'][str(region)]['r']['active'] for region in
                                       Office.ALL_REGIONS])
    d['national']['v'] = sum([d['by_region'][str(region)]['v'] for region in Office.ALL_REGIONS])

    return d
