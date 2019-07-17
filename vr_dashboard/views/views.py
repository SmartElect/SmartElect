# Python imports
import codecs
from collections import defaultdict, OrderedDict
import csv
from datetime import datetime, timedelta
import json
import logging
import numbers
import re

# 3rd party imports
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.template.defaultfilters import date as date_filter
from django.urls import reverse
from django.utils.timezone import now, utc
from django.utils.translation import pgettext
from django.utils.translation import ugettext as _

# Project imports
from libya_elections.constants import LIBYA_DATE_FORMAT
from libya_elections.phone_numbers import format_phone_number
from libya_elections.utils import should_hide_public_view
from libya_site.utils import intcomma, intcomma_if
from register.models import Office, RegistrationCenter
from register.utils import center_checkin_times
from reporting_api.constants import INACTIVE_FOR_ELECTION, POLLING_CENTER_CODE, \
    POLLING_CENTER_COPY_OF, PRELIMINARY_VOTE_COUNTS
from reporting_api.reports import calc_yesterday, election_key, \
    election_day_polling_center_log_key,\
    election_day_polling_center_table_key, parse_iso_datetime, printable_iso_datetime,\
    retrieve_report, ELECTION_DAY_BY_COUNTRY_KEY, ELECTION_DAY_HQ_REPORTS_KEY, \
    ELECTION_DAY_POLLING_CENTERS_TABLE_KEY, \
    ELECTION_DAY_METADATA_KEY, ELECTION_DAY_OFFICES_TABLE_KEY, \
    REGISTRATION_POINTS_CR_BY_COUNTRY_KEY, REGISTRATION_POINTS_NR_BY_COUNTRY_KEY, \
    REGISTRATION_POINTS_CR_BY_OFFICE_KEY, REGISTRATION_POINTS_NR_BY_OFFICE_KEY, \
    REGISTRATION_POINTS_CR_BY_REGION_KEY, REGISTRATION_POINTS_NR_BY_REGION_KEY, \
    REGISTRATION_POINTS_CR_BY_SUBCONSTITUENCY_KEY, REGISTRATION_POINTS_NR_BY_SUBCONSTITUENCY_KEY, \
    REGISTRATIONS_BY_COUNTRY_KEY, REGISTRATIONS_BY_OFFICE_KEY, REGISTRATIONS_BY_REGION_KEY, \
    REGISTRATIONS_BY_POLLING_CENTER_KEY, REGISTRATIONS_BY_PHONE_KEY, \
    REGISTRATIONS_BY_SUBCONSTITUENCY_KEY, REGISTRATIONS_CSV_COUNTRY_STATS_KEY, \
    REGISTRATIONS_CSV_OFFICE_STATS_KEY, REGISTRATIONS_CSV_REGION_STATS_KEY, \
    REGISTRATIONS_CSV_SUBCONSTITUENCY_STATS_KEY, REGISTRATIONS_METADATA_KEY, \
    REGISTRATIONS_OFFICE_STATS_KEY, REGISTRATIONS_REGION_STATS_KEY, REGISTRATIONS_STATS_KEY, \
    REGISTRATIONS_DAILY_BY_OFFICE_KEY, REGISTRATIONS_DAILY_BY_SUBCONSTITUENCY_KEY, \
    REGISTRATIONS_SUBCONSTITUENCY_STATS_KEY
from voting.models import Election
from vr_dashboard.forms import StartEndReportForm

logger = logging.getLogger(__name__)

# The VR dashboard currently reports counts of registrations prior to
# the Constitutional Drafting Assembly registration period.  The cutoff
# date for that was 2014-04-23.  The CDA date could be edited here for
# testing the pre-CDA counters with test data that only has newer
# registration dates.
#
# The entire feature will presumably be removed in the future.
CDA_DATE_STR = '2014-04-23'
CDA_DATE = datetime.strptime(CDA_DATE_STR, '%Y-%m-%d')

UNUSED_CENTER_ID = 99999999  # valid syntactically, but not used in actual data
FORMAT_QUERY_ARG = 'format'  # query argument to control response format on some pages
ELECTION_QUERY_ARG = 'election'  # query argument to select election by id
# if the data format changes, bump the version number
ELECTION_SESSION_KEY = 'SelElectV1'

PERIOD_VOTES_REPORTED_MESSAGE = _("Period {period} Votes Reported: {count}")

# Coloring by quartile not currently desired
# COLORS = {"purple": ["#F4E3FF", "#EBCFFC", "#DFB1FC", "#D595FC"],
#           "pink": ["#FAE6EE", "#FACFE0", "#F7B0CC", "#FA7FB0"],
#           "blue": ["#DBEFFF", "#BFE2FF", "#A1D5FF", "#80C6FF"],
#           "orange": ["#FFFFD4", "#FED98E", "#FE9929", "#CC4C02"],
#           "none": ["", "", "", ""]}
COLORS = {}


def quartile(arr, val):
    """ Return the quartile (0-3) of val in arr. """
    sorted_array = sorted(arr)
    interval_length = len(sorted_array) / 4.0
    return int(sorted_array.index(val) / interval_length)


def cell_color_by_quartile(color_family, arr, val):
    """ Find the color within the named color family for the cell with value val,
    based on the quartile of arr in which val appears. """
    if COLORS:
        return COLORS[color_family][quartile(arr, val)]
    else:
        return ""


def fmt_percent(x, total):
    """ Compute percent as x/total, format for a table cell. """
    if total == 0:
        percent = 0
    else:
        percent = float(x) / total * 100
    return str(round(percent, 2)) + '%'


def build_headline(last_updated, headline_stats):
    """ Build the headline that appears at the top of most VR dashboard pages. """
    males_total, females_total = headline_stats['males'], headline_stats['females']
    return _("As of {date} at {time} {total} people have registered on the High National "
             "Elections Commission SMS Voter Register. {num_women} of the registrants are women "
             "and {num_men} are men.").format(date=last_updated.strftime('%d/%m'),
                                              time=last_updated.strftime('%H:%M'),
                                              total=intcomma(males_total + females_total),
                                              num_women=intcomma(females_total),
                                              num_men=intcomma(males_total))


def handle_missing_report(request, page_flags, extra_args=None, template='vr_dashboard/error.html'):
    """ Return a 503 error page for a view when the report can't be retrieved from
    Redis.  Presumably the report hasn't yet been generated.

    The page will show the normal VR dashboard navigation; one page flag is
    needed by the template to indicate the current page within that navigation.
    """
    logger.error('A report is currently unavailable')
    msg = _("Data for this report is currently being generated.  Please try again later.")
    args = {
        'error_msg': msg,
        'request': request
    }
    if isinstance(page_flags, str):
        page_flags = [page_flags]
    for page_flag in page_flags:
        args[page_flag] = True
    if extra_args:
        args.update(extra_args)
    return render(request, template, args, status=503)


def handle_invalid_election(request, page_flag, extra_args=None):
    return handle_missing_report(request, [page_flag, 'staff_page'], extra_args,
                                 template='vr_dashboard/polling_error.html')


def handle_missing_election_report(request, election, page_flag):
    extra_args = {
        'elections': Election.objects.all(),
        'selected_election': election,
    }
    return handle_missing_report(request, [page_flag, 'staff_page'], extra_args,
                                 template='vr_dashboard/polling_error.html')


# public page
def redirect_to_national(request):
    return redirect('vr_dashboard:national')


# public page
def national(request):
    if should_hide_public_view(request):
        return redirect(settings.PUBLIC_REDIRECT_URL)
    page_flag = 'national_page'
    by_country, metadata, raw_stats, nr_by_country, cr_by_country = \
        retrieve_report([REGISTRATIONS_BY_COUNTRY_KEY,
                         REGISTRATIONS_METADATA_KEY,
                         REGISTRATIONS_STATS_KEY,
                         REGISTRATION_POINTS_NR_BY_COUNTRY_KEY,
                         REGISTRATION_POINTS_CR_BY_COUNTRY_KEY])
    if by_country is None:
        return handle_missing_report(request, page_flag)

    last_updated = parse_iso_datetime(metadata['last_updated'])
    # Just keep country-wide data for first country in list.
    # A visual redesign is needed to support more than one country, since
    # the country is in <thead></thead>.
    country_wide_data = by_country[0] if by_country else {}
    country_name = country_wide_data['country'] \
        if 'country' in country_wide_data else 'no data available'

    age_groupings = metadata['demographic_breakdowns']['by_age']
    dates = metadata['dates']
    yesterday_date, yesterday_date_str = calc_yesterday(dates)

    by_age = []
    for age in age_groupings:
        age_count = country_wide_data.get(age, 0)
        by_age.append((age, age_count))

    totals = [0, 0]  # male and female
    for d in dates:
        for i in range(len(totals)):
            try:
                totals[i] += country_wide_data[d][i]
            except KeyError:
                raise Exception("Bug 951: d: %s, dates: %r, country_wide_data: %r" %
                                (d, dates, country_wide_data))

    yesterday_totals = country_wide_data[yesterday_date_str] if yesterday_date_str else [0, 0]

    groups = [{'name': country_name,
               'm': totals[0],
               'm_color': cell_color_by_quartile("blue", [totals[0]], totals[0]),
               'f': totals[1],
               'f_color': cell_color_by_quartile("pink", [totals[1]], totals[1]),
               't': sum(totals),
               't_color': cell_color_by_quartile("purple", [sum(totals)], sum(totals)),
               'm_yesterday': yesterday_totals[0],
               'm_yesterday_color':
               cell_color_by_quartile("blue", [yesterday_totals[0]], yesterday_totals[0]),
               'f_yesterday': yesterday_totals[1],
               'f_yesterday_color':
               cell_color_by_quartile("pink", [yesterday_totals[1]], yesterday_totals[1]),
               't_yesterday': sum(yesterday_totals),
               't_yesterday_color':
               cell_color_by_quartile("purple", [sum(yesterday_totals)], sum(yesterday_totals)),
               }]
    headline = build_headline(last_updated, raw_stats['headline'])
    template_args = {
        'country': country_name,
        'by_age': by_age,
        'nr_by_country': nr_by_country,
        'cr_by_country': cr_by_country,
        'new_reg_chart': True,
        'cum_reg_chart': True,
        'yesterday': yesterday_date.strftime('%d/%m') if yesterday_date else '',
        'groups': groups,
        page_flag: True,
        'registration_stats_page': True,
        'headline_stats': headline,
        'last_updated': last_updated
    }
    return render(request, 'vr_dashboard/national.html', template_args)


def finalize_offices_stats(stats):
    keys_in_order = sorted([int(k) for k in stats.keys() if k != 'total'])

    office_objects = Office.objects.filter(id__in=keys_in_order)
    males_by_office = []
    females_by_office = []
    total_by_office = []
    males_yesterday_by_office = []
    females_yesterday_by_office = []
    total_yesterday_by_office = []

    office_info = []
    for offices_index, office_id in enumerate(keys_in_order):
        oi = stats[str(office_id)]
        office_info.append(oi)
        oi['name'] = office_objects[offices_index].name
        oi['pct_f'] = fmt_percent(oi['f'], oi['t'])
        oi['pct_f_yesterday'] = \
            fmt_percent(oi['f_yesterday'], oi['t_yesterday'])

        males_by_office.append(oi['m'])
        females_by_office.append(oi['f'])
        total_by_office.append(oi['t'])

        males_yesterday_by_office.append(oi['m_yesterday'])
        females_yesterday_by_office.append(oi['f_yesterday'])
        total_yesterday_by_office.append(oi['m_yesterday'] + oi['f_yesterday'])

    totals = stats['total']

    totals['pct_f'] = fmt_percent(totals['f'], totals['t'])
    totals['pct_f_yesterday'] = fmt_percent(totals['f_yesterday'], totals['t_yesterday'])

    # colorize based on relative quantity
    for i, oi in enumerate(office_info):
        oi['m_color'] = cell_color_by_quartile("blue", males_by_office,
                                               males_by_office[i])
        oi['f_color'] = cell_color_by_quartile("pink", females_by_office,
                                               females_by_office[i])
        oi['t_color'] = cell_color_by_quartile("purple", total_by_office,
                                               total_by_office[i])

        oi['m_yesterday_color'] = cell_color_by_quartile("blue", males_yesterday_by_office,
                                                         males_yesterday_by_office[i])
        oi['f_yesterday_color'] = cell_color_by_quartile("pink", females_yesterday_by_office,
                                                         females_yesterday_by_office[i])
        oi['t_yesterday_color'] = cell_color_by_quartile("purple", total_yesterday_by_office,
                                                         total_yesterday_by_office[i])

    totals['m_color'] = cell_color_by_quartile("blue", males_by_office + [totals['m']],
                                               totals['m'])
    totals['f_color'] = cell_color_by_quartile("pink", females_by_office + [totals['f']],
                                               totals['f'])
    totals['t_color'] = cell_color_by_quartile("purple", total_by_office + [totals['t']],
                                               totals['t'])
    totals['m_yesterday_color'] = \
        cell_color_by_quartile("blue", males_yesterday_by_office + [totals['m_yesterday']],
                               totals['m_yesterday'])
    totals['f_yesterday_color'] = \
        cell_color_by_quartile("pink", females_yesterday_by_office + [totals['f_yesterday']],
                               totals['f_yesterday'])
    totals['t_yesterday_color'] = \
        cell_color_by_quartile("purple", total_yesterday_by_office + [totals['t_yesterday']],
                               totals['t_yesterday'])

    return office_info, totals


# public page
def offices(request):
    if should_hide_public_view(request):
        return redirect(settings.PUBLIC_REDIRECT_URL)
    page_flag = 'offices_page'
    metadata, office_stats, raw_stats, nr_by_office, cr_by_office = \
        retrieve_report([REGISTRATIONS_METADATA_KEY,
                         REGISTRATIONS_OFFICE_STATS_KEY,
                         REGISTRATIONS_STATS_KEY,
                         REGISTRATION_POINTS_NR_BY_OFFICE_KEY,
                         REGISTRATION_POINTS_CR_BY_OFFICE_KEY])
    if metadata is None:
        return handle_missing_report(request, page_flag)

    last_updated = parse_iso_datetime(metadata['last_updated'])
    dates = metadata['dates']
    yesterday_date, yesterday_date_str = calc_yesterday(dates)
    office_info, totals = finalize_offices_stats(office_stats)

    headline = build_headline(last_updated, raw_stats['headline'])
    template_args = {'groups': office_info,
                     'yesterday': yesterday_date.strftime('%d/%m') if yesterday_date else '',
                     'totals': totals,
                     page_flag: True,
                     'registration_stats_page': True,
                     'headline_stats': headline,
                     'nr': nr_by_office,
                     'cr': cr_by_office,
                     'new_reg_chart': True,
                     'cum_reg_chart': True,
                     'last_updated': last_updated}
    return render(request, 'vr_dashboard/offices.html', template_args)


@user_passes_test(lambda user: user.is_staff)
def offices_detail(request):
    """ Like offices(), but omits %female from cumulative-totals and last-day total and adds
    a column for each age breakdown. """
    page_flag = 'offices_detail_page'
    metadata, office_stats, raw_stats, nr_by_office, cr_by_office = \
        retrieve_report([REGISTRATIONS_METADATA_KEY,
                         REGISTRATIONS_OFFICE_STATS_KEY,
                         REGISTRATIONS_STATS_KEY,
                         REGISTRATION_POINTS_NR_BY_OFFICE_KEY,
                         REGISTRATION_POINTS_CR_BY_OFFICE_KEY])
    if metadata is None:
        return handle_missing_report(request, page_flag)

    last_updated = parse_iso_datetime(metadata['last_updated'])
    age_groupings = metadata['demographic_breakdowns']['by_age']
    dates = metadata['dates']
    yesterday_date, yesterday_date_str = calc_yesterday(dates)
    office_info, totals = finalize_offices_stats(office_stats)

    headline = build_headline(last_updated, raw_stats['headline'])
    template_args = {'office_info': office_info,
                     'yesterday': yesterday_date.strftime('%d/%m') if yesterday_date else '',
                     'age_groupings': age_groupings,
                     'totals': totals,
                     page_flag: True,
                     'registration_stats_page': True,
                     'headline_stats': headline,
                     'nr': nr_by_office,
                     'cr': cr_by_office,
                     'new_reg_chart': True,
                     'cum_reg_chart': True,
                     'last_updated': last_updated}
    return render(request, 'vr_dashboard/offices_detail.html', template_args)


@user_passes_test(lambda user: user.is_staff)
def weekly(request):
    page_flag = 'weekly_page'
    office_breakdowns, metadata, raw_stats, nr_by_country = \
        retrieve_report([REGISTRATIONS_BY_OFFICE_KEY,
                         REGISTRATIONS_METADATA_KEY,
                         REGISTRATIONS_STATS_KEY,
                         REGISTRATION_POINTS_NR_BY_COUNTRY_KEY])
    if office_breakdowns is None:
        return handle_missing_report(request, page_flag)

    last_updated = parse_iso_datetime(metadata['last_updated'])

    office_info = [{'id': ob['office_id']} for ob in office_breakdowns]
    for oi in office_info:
        oi['name'] = Office.objects.get(id=oi['id']).name

    dates = metadata['dates']
    if dates:
        last_7 = dates[-7:]  # smaller during first week
        last_7_fmt = [datetime.strptime(d, '%Y-%m-%d').strftime('%d/%m') for d in last_7]
        last_7_indexes = [i for i in range(len(last_7))]

        # get date ranges for last <= 4 weeks
        #
        # if the last date is Thursday, March 20, the last week will be the enclosing
        # Sunday-Saturday, or March 16-22.
        start_day = datetime.strptime(dates[0], '%Y-%m-%d')
        last_day = datetime.strptime(dates[-1], '%Y-%m-%d')
        end_of_last_week = last_day + timedelta((12 - last_day.weekday()) % 7)
        start_of_last_week = end_of_last_week - timedelta(6)

        last_four_weeks = []
        last_four_weeks_fmt = []
        cur_start = start_of_last_week
        while len(last_four_weeks) < 4:
            end_of_cur_week = cur_start + timedelta(6)
            if start_day > end_of_cur_week:
                break
            last_four_weeks.append((cur_start, end_of_cur_week))
            last_four_weeks_fmt.append((cur_start.strftime('%d/%m'),
                                        end_of_cur_week.strftime('%d/%m')))
            cur_start -= timedelta(7)
        last_four_weeks = list(reversed(last_four_weeks))
        last_four_weeks_fmt = list(reversed(last_four_weeks_fmt))
    else:
        last_four_weeks = last_four_weeks_fmt = last_7 = last_7_fmt = last_7_indexes = []

    # across all offices, we need to get this data:
    #   male+female for each of last 7 days
    #   male+female for each of last 4 weeks
    #   male+female [prior to CDA date
    #   cumulative_male
    #   cumulative_female

    global_info = {'last_seven': [0] * len(last_7),
                   'last_four_weeks': [0] * len(last_four_weeks),
                   'yesterday': 0,
                   'male': 0,
                   'female': 0,
                   'pre_cda': 0}

    for i, ob in enumerate(office_breakdowns):
        oi = office_info[i]

        # for each office, we need to get this data:
        #   male+female for each of last 7 days
        #   male+female for each of last 4 weeks
        #   male+female prior to CDA date
        #   cumulative male
        #   cumulative female
        # from cumulative-male and cumulative-female we'll make the
        # trivial calculations of percent-female and total

        total_male = total_female = 0
        last_7_totals = []
        pre_cda_total = 0

        oi['last_four_weeks'] = [0] * len(last_four_weeks)

        if dates:
            yesterday_date, yesterday_date_str = calc_yesterday(dates)

        for d in dates:
            d_dt = datetime.strptime(d, '%Y-%m-%d')
            if d in ob:
                date_males, date_females = ob[d]
            else:
                date_males, date_females = 0, 0
            total_male += date_males
            total_female += date_females

            if d == yesterday_date_str:
                global_info['yesterday'] += date_males + date_females

            if d in last_7:
                last_7_totals.append(date_males + date_females)
                global_info['last_seven'][last_7.index(d)] += date_males + date_females

            if d_dt < CDA_DATE:
                pre_cda_total += date_males + date_females

            for j, date_range in enumerate(last_four_weeks):
                if date_range[0] <= d_dt <= date_range[1]:
                    oi['last_four_weeks'][j] += date_males + date_females
                    global_info['last_four_weeks'][j] += date_males + date_females

        oi['last_seven'] = last_7_totals

        oi['pre_cda'] = pre_cda_total
        global_info['pre_cda'] += pre_cda_total

        oi['last_seven_colors'] = []
        for j in range(len(last_7_totals)):
            oi['last_seven_colors'].append(cell_color_by_quartile("orange", last_7_totals,
                                                                  last_7_totals[j]))

        total = total_male + total_female
        oi['total'] = total
        oi['pct_female'] = 0.0 if total == 0 else float(total_female) / total
        oi['pct_female_fmt'] = fmt_percent(total_female, total)

        global_info['male'] += total_male
        global_info['female'] += total_female

    global_info['total'] = global_info['male'] + global_info['female']
    global_info['pct_female_fmt'] = fmt_percent(global_info['female'], global_info['total'])
    global_info['pct_male_fmt'] = fmt_percent(global_info['male'], global_info['total'])

    # now go back and color cells

    global_info['last_seven_colors'] = []
    for i in range(len(last_7)):
        global_info['last_seven_colors']\
            .append(cell_color_by_quartile("orange",
                                           global_info['last_seven'],
                                           global_info['last_seven'][i]))
    row_totals = [oi['total'] for _oi in office_info]
    pct_female = [oi['pct_female'] for _oi in office_info]
    for oi in office_info:
        oi['total_color'] = cell_color_by_quartile("blue", row_totals, oi['total'])
        oi['pct_female_color'] = cell_color_by_quartile("pink", pct_female, oi['pct_female'])

    headline = build_headline(last_updated, raw_stats['headline'])
    template_args = {'office_info': office_info,
                     'global_info': global_info,
                     'last_seven': last_7_fmt,
                     'last_seven_indexes': last_7_indexes,
                     'last_seven_actual': len(last_7_indexes),
                     'last_four_weeks': last_four_weeks_fmt,
                     'num_weeks': len(last_four_weeks),
                     'num_weeks_range': list(range(len(last_four_weeks))),
                     page_flag: True,
                     'registration_stats_page': True,
                     'nr': nr_by_country,
                     'new_reg_chart': True,
                     'headline_stats': headline,
                     'last_updated': last_updated}
    return render(request, 'vr_dashboard/weekly.html', template_args)


def last_seven_dates(dates):
    """ Return the last seven of dates, which are strings of the
    form '%Y-%m-%d', in increasing order of date.

    If the last date is today, ignore it.
    Fewer than seven may be returned.

    Like the Ruby implementation, this doesn't account for days
    with no data, so the "Last 7 Days" column heading on the SMS
    page may not be correct.
    """
    if dates and dates[-1] == now().date().strftime('%Y-%m-%d'):
        # ignore data from today
        dates = dates[:-1]
    return dates[-7:]


def compute_message_stats(stats, dates):
    """ Return the following stats for SMS messages of a particular
    type:
        overall count
        count for the last seven dates
        count for "yesterday"
        date of "yesterday" in %d/%m format

    The input dictionary stats has counts for dates, though not
    necessarily for any particular date.  The date keys are of the form
    '%Y-%m-%d' and potential dates are given in the input list dates.
    """
    yesterday_date, yesterday_date_str = calc_yesterday(dates)
    last_week = last_seven_dates(dates)
    all_counts_by_date = [stats.get(date, 0) for date in dates]
    total = sum(all_counts_by_date)
    counts_for_last_seven_dates = [stats.get(date, 0) for date in last_week]
    total_last_7 = sum(counts_for_last_seven_dates)
    stats = {'total_last_7': total_last_7,
             'total': total,
             'last': stats.get(yesterday_date_str, 0),
             'last_date': yesterday_date.strftime('%d/%m') if yesterday_date else ''
             }
    return stats


@user_passes_test(lambda user: user.is_staff)
def sms(request):
    page_flag = 'sms_page'
    raw_stats, metadata = retrieve_report([REGISTRATIONS_STATS_KEY,
                                           REGISTRATIONS_METADATA_KEY])
    if raw_stats is None:
        return handle_missing_report(request, page_flag)

    last_updated = parse_iso_datetime(metadata['last_updated'])
    sms_stats = compute_message_stats(raw_stats['sms_stats']['messages'], metadata['dates'])

    # Compute summary stats for each SMS message type present in the dictionary.
    # SMS message types with no matching messages (for MESSAGES_QUERY) won't be present.
    stats_by_sms_type = []
    for sms_type, raw in raw_stats['message_stats'].items():
        computed = compute_message_stats(raw, metadata['dates'])
        computed['translated_sms_type'] = _(sms_type)
        stats_by_sms_type.append(computed)

    headline = build_headline(last_updated, raw_stats['headline'])
    template_args = {'raw_stats': raw_stats,
                     'sms_stats': sms_stats,
                     'message_stats_by_type': stats_by_sms_type,
                     'headline_stats': headline,
                     page_flag: True,
                     'registration_stats_page': True,
                     'last_updated': last_updated}
    return render(request, 'vr_dashboard/sms.html', template_args)


@user_passes_test(lambda user: user.is_staff)
def reports(request):
    page_flag = 'reports_page'
    raw_stats, metadata = retrieve_report([REGISTRATIONS_STATS_KEY,
                                           REGISTRATIONS_METADATA_KEY])
    if raw_stats is None:
        return handle_missing_report(request, page_flag)

    status_code = 200
    if request.method == 'POST':
        # Button on the reports page requests a date-limited daily csv report
        form = StartEndReportForm(data=request.POST)
        if form.is_valid():
            url = reverse(
                'vr_dashboard:daily-csv-with-dates',
                kwargs={
                    'from_date': form.cleaned_data['from_date'].strftime(LIBYA_DATE_FORMAT),
                    'to_date': form.cleaned_data['to_date'].strftime(LIBYA_DATE_FORMAT),
                }
            )
            return redirect(url)
        status_code = 400
    else:
        form = StartEndReportForm()

    last_updated = parse_iso_datetime(metadata['last_updated'])
    headline = build_headline(last_updated, raw_stats['headline'])
    template_args = {
        'headline_stats': headline,
        page_flag: True,
        'registration_stats_page': True,
        'last_updated': last_updated,
        'start_end_report_form': form,
    }
    return render(request, 'vr_dashboard/reports.html', template_args, status=status_code)


def cells_by_region(language_code, table, stats, metadata, page_flag):
    m_by_region = [stats[r]['m'] for r in stats.keys() if r != 'total']
    f_by_region = [stats[r]['f'] for r in stats.keys() if r != 'total']
    t_by_region = [stats[r]['t'] for r in stats.keys() if r != 'total']
    m_yesterday_by_region = [stats[r]['m_yesterday'] for r in stats.keys() if r != 'total']
    f_yesterday_by_region = [stats[r]['f_yesterday'] for r in stats.keys() if r != 'total']
    t_yesterday_by_region = [stats[r]['t_yesterday'] for r in stats.keys() if r != 'total']

    region_info = []
    if page_flag == 'subconstituencies_page':
        keys = sorted([k for k in stats.keys() if k != 'total'], key=int)
        name_field = 'english_name' if language_code == 'en' else 'arabic_name'
        display_names = {str(subcon['code']): str(subcon['code']) + ' ' + subcon[name_field]
                         for subcon in metadata['subconstituencies']}
    else:
        keys = [k for k in stats.keys() if k != 'total']
        display_names = {k: _(k) for k in stats.keys()}
    for k in keys:
        row = {'name': k,
               'display_name': display_names[k],
               'm': stats[k]['m'],
               'm_color': cell_color_by_quartile('blue', m_by_region,
                                                 stats[k]['m']),
               'f': stats[k]['f'],
               'f_color': cell_color_by_quartile('pink', f_by_region,
                                                 stats[k]['f']),
               't': stats[k]['t'],
               't_color': cell_color_by_quartile('purple', t_by_region,
                                                 stats[k]['t']),
               'm_yesterday': stats[k]['m_yesterday'],
               'm_yesterday_color': cell_color_by_quartile('blue', m_yesterday_by_region,
                                                           stats[k]['m_yesterday']),
               'f_yesterday': stats[k]['f_yesterday'],
               'f_yesterday_color': cell_color_by_quartile('pink', f_yesterday_by_region,
                                                           stats[k]['f_yesterday']),
               't_yesterday': stats[k]['t_yesterday'],
               't_yesterday_color': cell_color_by_quartile('purple', t_yesterday_by_region,
                                                           stats[k]['t_yesterday']),
               }
        region_info.append(row)

    # totals could be hard-coded to the color value of the 4th quartile
    last_region = len(table)  # value arrays have one more cell
    total_data = {'m': sum(m_by_region),
                  'm_color': cell_color_by_quartile('blue', m_by_region + [sum(m_by_region)],
                                                    sum(m_by_region)),
                  'f': sum(f_by_region),
                  'f_color': cell_color_by_quartile('pink', f_by_region + [sum(f_by_region)],
                                                    sum(f_by_region)),
                  't': sum(t_by_region),
                  't_color': cell_color_by_quartile('purple', t_by_region + [sum(t_by_region)],
                                                    sum(t_by_region)),
                  'm_yesterday': sum(m_yesterday_by_region),
                  'm_yesterday_color': cell_color_by_quartile('blue',
                                                              m_yesterday_by_region
                                                              + [sum(m_yesterday_by_region)],
                                                              sum(m_yesterday_by_region)),
                  'f_yesterday': sum(f_yesterday_by_region),
                  'f_yesterday_color': cell_color_by_quartile('pink',
                                                              f_yesterday_by_region
                                                              + [sum(f_yesterday_by_region)],
                                                              sum(f_yesterday_by_region)),
                  't_yesterday': sum(t_yesterday_by_region),
                  't_yesterday_color': cell_color_by_quartile('purple',
                                                              t_yesterday_by_region
                                                              + [sum(t_yesterday_by_region)],
                                                              sum(t_yesterday_by_region)),
                  }

    return region_info, total_data, last_region


def report_regional_grouping(request, grouping, region_stats, metadata, raw_stats, page_flag,
                             nr, cr):
    dates = metadata['dates']
    yesterday_date, yesterday_date_str = calc_yesterday(dates)

    age_groupings = metadata['demographic_breakdowns']['by_age']
    last_updated = parse_iso_datetime(metadata['last_updated'])

    region_info, total_data, last_region = cells_by_region(request.LANGUAGE_CODE, grouping,
                                                           region_stats, metadata, page_flag)

    headline = build_headline(last_updated, raw_stats['headline'])
    template_args = {'stats': region_stats,
                     'regions': region_info,
                     'yesterday': yesterday_date.strftime('%d/%m') if yesterday_date else '',
                     'headline_stats': headline,
                     'nr': nr,
                     'cr': cr,
                     'new_reg_chart': True,
                     'cum_reg_chart': True,
                     'totals': total_data,
                     'age_groupings': age_groupings,
                     page_flag: True,
                     'registration_stats_page': True,
                     'last_updated': last_updated}
    return render(request, 'vr_dashboard/regions.html', template_args)


# public page
def regions(request):
    if should_hide_public_view(request):
        return redirect(settings.PUBLIC_REDIRECT_URL)
    page_flag = 'regions_page'
    grouping, metadata, raw_stats, region_stats, nr_by_region, cr_by_region = \
        retrieve_report([REGISTRATIONS_BY_REGION_KEY,
                         REGISTRATIONS_METADATA_KEY,
                         REGISTRATIONS_STATS_KEY,
                         REGISTRATIONS_REGION_STATS_KEY,
                         REGISTRATION_POINTS_NR_BY_REGION_KEY,
                         REGISTRATION_POINTS_CR_BY_REGION_KEY])
    if grouping is None:
        return handle_missing_report(request, page_flag)

    return report_regional_grouping(request, grouping, region_stats, metadata, raw_stats,
                                    page_flag, nr_by_region, cr_by_region)


@user_passes_test(lambda user: user.is_staff)
def subconstituencies(request):
    page_flag = 'subconstituencies_page'
    grouping, metadata, raw_stats, region_stats, nr_by_subconstituency, cr_by_subconstituency = \
        retrieve_report([REGISTRATIONS_BY_SUBCONSTITUENCY_KEY,
                         REGISTRATIONS_METADATA_KEY,
                         REGISTRATIONS_STATS_KEY,
                         REGISTRATIONS_SUBCONSTITUENCY_STATS_KEY,
                         REGISTRATION_POINTS_NR_BY_SUBCONSTITUENCY_KEY,
                         REGISTRATION_POINTS_CR_BY_SUBCONSTITUENCY_KEY])
    if grouping is None:
        return handle_missing_report(request, page_flag)

    return report_regional_grouping(request, grouping, region_stats, metadata, raw_stats,
                                    page_flag, nr_by_subconstituency, cr_by_subconstituency)


def get_csv_writer(response):
    """ Return a CSV writer that will encode in UTF-16LE, after prefixing the
    body with a BOM.

    Presumably there are other ways to make Excel happy, but that's what
    the previous Ruby implementation of this feature does, and omitting the
    BOM is not sufficient.
    (Tested with Excel from Office 2010 on Windows 8.1)
    """
    response.write(codecs.BOM_UTF16_LE)
    return csv.writer(response, delimiter='\t')


@user_passes_test(lambda user: user.is_staff)
def csv_report(request):
    page_flag = 'csv_page'
    data = dict()
    metadata, data['countries'], data['offices'], data['regions'], data['subconstituencies'] = \
        retrieve_report([REGISTRATIONS_METADATA_KEY, REGISTRATIONS_CSV_COUNTRY_STATS_KEY,
                         REGISTRATIONS_CSV_OFFICE_STATS_KEY, REGISTRATIONS_CSV_REGION_STATS_KEY,
                         REGISTRATIONS_CSV_SUBCONSTITUENCY_STATS_KEY])
    if metadata is None:
        return handle_missing_report(request, page_flag)

    age_groupings = metadata['demographic_breakdowns']['by_age']

    tables = ["Countries", "Offices", "Regions", "Subconstituencies"]
    header = [_("Group"), _("Total"), _("Total M"), _("Total F"), _("Yesterday"), _("Yesterday M"),
              _("Yesterday F")]
    header += age_groupings

    last_updated = parse_iso_datetime(metadata['last_updated'])
    last_updated_msg = get_last_updated_msg(last_updated)

    response = HttpResponse(content_type='application/octet-stream', charset='utf-16le')
    client_filename = get_csv_filename(request, 'registrations')

    preferred_label = 'english_name' if request.LANGUAGE_CODE == 'en' else 'arabic_name'

    response['Content-Disposition'] = 'attachment; filename="%s"' % client_filename
    w = get_csv_writer(response)
    w.writerow([last_updated_msg])
    for table in tables:
        w.writerow([_(table)])
        w.writerow(header)
        for row in data[table.lower()]:
            if isinstance(row['label'], str):
                assert row['label_translated']
                label = _(row['label'])
            elif preferred_label in row['label']:
                label = row['label'][preferred_label]
            else:
                label = row['label']['name']
            item = [label, row['total'][0], row['total'][1], row['total'][2],
                    row['yesterday'][0], row['yesterday'][1], row['yesterday'][2]]
            for age in age_groupings:
                item.append(row[age])
            for i, field in enumerate(item):
                if isinstance(field, numbers.Number):
                    item[i] = str(field)

            w.writerow(item)

    return response


@user_passes_test(lambda user: user.is_staff)
def csv_daily_report(request, from_date=None, to_date=None):
    """
    Return a csv file (actually tab separated) with a daily report,
    headers indicating the browser should prompt the user to save
    it rather than displaying it in the browser.

    Should either include both from and to date, or neither.
    If only one is given, it's ignored (but the URL patterns currently
    won't even allow that request to get to this view).

    NOTE: dates are in dd/mm/yyyy format, not the mm/dd/yyyy format
    we're probably used to.

    If either date isn't valid, or to is before from, returns 400.

    :param request: HttpRequest
    :param from_date: "DD/MM/YYYY" first date to include results for
    :param to_date: "DD/MM/YYYY" last date to include results for
    """
    page_flag = 'daily_csv_page'
    daily_by_office, daily_by_subconstituency, metadata = retrieve_report(
        [REGISTRATIONS_DAILY_BY_OFFICE_KEY,
         REGISTRATIONS_DAILY_BY_SUBCONSTITUENCY_KEY,
         REGISTRATIONS_METADATA_KEY]
    )
    if daily_by_office is None:
        return handle_missing_report(request, page_flag)

    last_updated = parse_iso_datetime(metadata['last_updated'])
    last_updated_msg = get_last_updated_msg(last_updated)

    parse_date = lambda s: datetime.strptime(s, LIBYA_DATE_FORMAT).date()

    response = HttpResponse(content_type='application/octet-stream', charset='utf-16le')
    if from_date and to_date:
        # For simplicity, use the strings to build the filename before we've
        # validated them. If they turn out not to be valid date strings, we
        # won't be using this filename anyway.
        client_filename = get_csv_filename(
            request,
            'daily_breakdown_%s-%s' % (from_date.replace('/', '-'), to_date.replace('/', '-')))
        try:
            from_date = parse_date(from_date)
            to_date = parse_date(to_date)
        except ValueError:
            return HttpResponseBadRequest("Bad date or dates")
    else:
        client_filename = get_csv_filename(request, 'daily_breakdown')

    response['Content-Disposition'] = 'attachment; filename="%s"' % client_filename

    w = get_csv_writer(response)
    w.writerow([last_updated_msg])

    title_column = 0 if request.LANGUAGE_CODE == 'en' else 1
    daily_by_office[0][title_column] = _('Office')
    # include all columns by default
    daily_by_office_columns_to_include = [
        True for x in range(len(daily_by_office[0]))]
    if from_date and to_date:
        # If there are date limits, figure out which columns we
        # should omit
        for i, field in enumerate(daily_by_office[0]):
            if i >= 2:
                date_str, m_f = field.split(' ')
                daily_by_office_columns_to_include[i] = \
                    from_date <= parse_date(date_str) <= to_date

    daily_by_subconstituency[0][title_column] = _('Subconstituency')
    # include all columns by default
    daily_by_subconstituency_columns_to_include = [
        True for x in range(len(daily_by_subconstituency[0]))]
    if from_date and to_date:
        # If there are date limits, figure out which columns we
        # should omit
        for i, field in enumerate(daily_by_subconstituency[0]):
            if i >= 2:
                date_str, m_f = field.split(' ')
                daily_by_subconstituency_columns_to_include[i] \
                    = from_date <= parse_date(date_str) <= to_date

    for row in daily_by_office:
        for i, field in enumerate(row[2:]):
            if isinstance(field, numbers.Number):
                row[i + 2] = str(field)
        filtered_row = [
            elt for i, elt in enumerate(row) if daily_by_office_columns_to_include[i]]
        w.writerow([filtered_row[title_column]] + filtered_row[2:])

    # Write empty row to separate the 2 tables
    w.writerow('')

    for row in daily_by_subconstituency:
        for i, field in enumerate(row[2:]):
            if isinstance(field, numbers.Number):
                row[i + 2] = str(field)
        filtered_row = [
            elt for i, elt in enumerate(row) if daily_by_subconstituency_columns_to_include[i]]
        w.writerow([filtered_row[title_column]] + filtered_row[2:])

    return response


@user_passes_test(lambda user: user.is_staff)
def center_csv_report(request):
    page_flag = 'center_csv_page'
    metadata, polling_centers = \
        retrieve_report([REGISTRATIONS_METADATA_KEY, REGISTRATIONS_BY_POLLING_CENTER_KEY])
    if metadata is None:
        return handle_missing_report(request, page_flag)

    header = [_("Center ID"), _("Name"), _("Total Registrations")]
    last_updated = parse_iso_datetime(metadata['last_updated'])
    last_updated_msg = get_last_updated_msg(last_updated)

    # convert list of dictionaries to a single dictionary with polling center
    # code as key, and total registrations for that center as value
    registrations_by_center_id = {
        center[POLLING_CENTER_CODE]: center['total']
        for center in polling_centers
    }

    response = HttpResponse(content_type='application/octet-stream', charset='utf-16le')
    client_filename = get_csv_filename(request, 'registrations_by_polling_center')
    response['Content-Disposition'] = 'attachment; filename="%s"' % client_filename
    w = get_csv_writer(response)
    w.writerow([last_updated_msg])
    w.writerow(header)

    # get a list of centers ordered by center_id (model default ordering),
    # excluding any centers which are not in our report
    centers_in_report = RegistrationCenter.objects.filter(
        center_id__in=registrations_by_center_id.keys())

    for center in centers_in_report:
        w.writerow([
            str(center.center_id),
            center.name,
            str(registrations_by_center_id[center.center_id])
        ])
    return response


@user_passes_test(lambda user: user.is_staff)
def phone_csv_report(request):
    page_flag = 'phone_csv_page'
    metadata, registrations_by_phone = \
        retrieve_report([REGISTRATIONS_METADATA_KEY, REGISTRATIONS_BY_PHONE_KEY])
    if metadata is None:
        return handle_missing_report(request, page_flag)

    header = [_("Phone Number"), _("Total Registrations")]
    last_updated = parse_iso_datetime(metadata['last_updated'])
    last_updated_msg = get_last_updated_msg(last_updated)

    response = HttpResponse(content_type='application/octet-stream', charset='utf-16le')
    client_filename = get_csv_filename(request, 'registrations_by_phone')
    response['Content-Disposition'] = 'attachment; filename="%s"' % client_filename
    w = get_csv_writer(response)
    w.writerow([last_updated_msg])
    w.writerow(header)

    for phone_number, registration_count in registrations_by_phone:
        w.writerow([
            str(phone_number),
            str(registration_count)
        ])
    return response


def get_response_format(request):
    """ Check the format query arg (if it exists) for the desired rendering.
    Return None if the request is invalid or the format otherwise. """
    valid_formats = ('csv', 'html')
    default_format = 'html'
    requested_format = request.GET.get(FORMAT_QUERY_ARG, default_format).lower()
    if requested_format in valid_formats:
        return requested_format
    return None


def get_chosen_election(request):
    """
    If election query arg is specified, user wants to switch elections; try to do so.
    Otherwise, grab previously-chosen election from session.

    If no election chosen or choice is not available, pick the default.

    As long as the election is available, store in the session.

    In the unexpected case that no election is found, make sure that a choice is
    not stored in the session.
    """
    election = None

    if ELECTION_QUERY_ARG in request.GET:
        try:
            chosen_election_id = int(request.GET[ELECTION_QUERY_ARG])
        except ValueError:
            chosen_election_id = None
    else:
        chosen_election_id = request.session.get(ELECTION_SESSION_KEY)

    if chosen_election_id is not None:
        try:
            election = Election.objects.get(id=chosen_election_id)
        except Election.DoesNotExist:
            pass

    if not election:
        election = Election.objects.get_most_current_election()

    if election:
        request.session[ELECTION_SESSION_KEY] = election.id
    elif ELECTION_SESSION_KEY in request.session:
        del request.session[ELECTION_SESSION_KEY]

    return election


def get_csv_filename(request, base):
    """ Generate a filename for a CSV file which includes the base
    name provided by the caller, the language code, the current date,
    and the .csv extension.
    """
    date = now().strftime('%d_%m_%Y')
    return '%s_%s_%s.csv' % (base, request.LANGUAGE_CODE, date)


def get_invalid_format_error(request):
    """ Build an HTTP error response to be used when somebody plays with
    the format=XXX argument to some of the pages and and doesn't provide
    a valid XXX.
    """
    msg = _('Response format is not supported.')
    return HttpResponseBadRequest(msg)


def get_last_updated_msg(last_updated):
    return _('Last Updated: %s') % date_filter(last_updated, 'H:i d-m-Y')


def emphasized_data(s):
    return '<span class="emphasized-data">{}</span>'.format(s) if s else ''


@user_passes_test(lambda user: user.is_staff)
def election_day(request):
    response_format = get_response_format(request)
    if not response_format:  # requested format invalid
        return get_invalid_format_error(request)
    page_flag = 'election_day_overview_page'
    election = get_chosen_election(request)
    if election is None:
        return handle_invalid_election(request, page_flag)
    metadata, offices_table, by_country = \
        retrieve_report([election_key(ELECTION_DAY_METADATA_KEY, election),
                         election_key(ELECTION_DAY_OFFICES_TABLE_KEY, election),
                         election_key(ELECTION_DAY_BY_COUNTRY_KEY, election)])
    if metadata is None:
        return handle_missing_election_report(request, election, page_flag)

    last_updated = parse_iso_datetime(metadata['last_updated'])
    last_updated_msg = get_last_updated_msg(last_updated)

    total_opened = 0
    total_not_opened = 0
    total_closed = 0

    total_not_reported = defaultdict(int)
    total_reported = defaultdict(int)

    for office in offices_table:
        if request.LANGUAGE_CODE == 'ar':
            office['name'] = office['arabic_name']
        else:
            office['name'] = office['english_name']
        office['opened_pct'] = fmt_percent(office['opened'], office['polling_center_count'])
        office['closed_pct'] = fmt_percent(office['closed'], office['polling_center_count'])

        total_opened += office['opened']
        total_not_opened += office['not_opened']
        total_closed += office['closed']

        for period in [1, 2, 3, 4]:
            total_not_reported[period] += office['not_reported_' + str(period)]
            total_reported[period] += office['votes_reported_' + str(period)]

    summary = {'name': _('Libya'),
               'by_country': by_country['Libya']['polling_center_count'],
               'opened': total_opened,
               'opened_pct': fmt_percent(total_opened,
                                         by_country['Libya']['polling_center_count']),
               'not_opened': total_not_opened,
               'not_reported_1': total_not_reported[1],
               'not_reported_2': total_not_reported[2],
               'not_reported_3': total_not_reported[3],
               'not_reported_4': total_not_reported[4],
               'closed': total_closed,
               'closed_pct': fmt_percent(total_closed,
                                         by_country['Libya']['polling_center_count'])
               }

    if response_format == 'csv':
        response = HttpResponse(content_type='application/octet-stream', charset='utf-16le')
        client_filename = get_csv_filename(request, 'election_day_overview')
        response['Content-Disposition'] = 'attachment; filename="%s"' % client_filename
        w = get_csv_writer(response)
        w.writerow([
            _('Election Day Overview')
        ])
        w.writerow([
            last_updated_msg
        ])
        w.writerow([
            _('Office'),
            _('Polling Center'),
            _('Opened'),
            _('Not Opened'),
            # Format "Not Reported Period n" carefully to use the same strings
            # which the HTML template uses.
            _('Not Reported') + ' ' + _('Period') + ' ' + '1',
            _('Not Reported') + ' ' + _('Period') + ' ' + '2',
            _('Not Reported') + ' ' + _('Period') + ' ' + '3',
            _('Not Reported') + ' ' + _('Period') + ' ' + '4',
            _('Closed')
        ])
        for office in offices_table:
            name_fmt = '%(name)s %(id)d' if request.LANGUAGE_CODE == 'ar' else '%(id)d %(name)s'
            args = {
                'id': office['office_id'],
                'name': office['name']
            }
            w.writerow([
                name_fmt % args,
                str(office['polling_center_count']),
                str(office['opened']),
                str(office['not_opened']),
                str(office['not_reported_1']),
                str(office['not_reported_2']),
                str(office['not_reported_3']),
                str(office['not_reported_4']),
                str(office['closed'])
            ])
        w.writerow([
            summary['name'],
            str(summary['by_country']),
            str(summary['opened']),
            str(summary['not_opened']),
            str(summary['not_reported_1']),
            str(summary['not_reported_2']),
            str(summary['not_reported_3']),
            str(summary['not_reported_4']),
            str(summary['closed'])
        ])
        return response

    headline = \
        {'as_of_datetime':
         _("As of {time} on {date}:").format(time=last_updated.strftime('%H:%M'),
                                             date=last_updated.strftime('%d/%m')),

         'open_centers':
         _("{count} centers have opened").format(count=emphasized_data(intcomma(total_opened))),

         'unopen_centers':
         _("{count} centers have not opened").format(
             count=emphasized_data(intcomma(total_not_opened))),

         'period1': PERIOD_VOTES_REPORTED_MESSAGE.format(
             count=emphasized_data(intcomma(total_reported[1])), period=1),

         'period2': PERIOD_VOTES_REPORTED_MESSAGE.format(
             count=emphasized_data(intcomma(total_reported[2])), period=2),

         'period3': PERIOD_VOTES_REPORTED_MESSAGE.format(
             count=emphasized_data(intcomma(total_reported[3])), period=3),

         'period4': PERIOD_VOTES_REPORTED_MESSAGE.format(
             count=emphasized_data(intcomma(total_reported[4])), period=4)
         }
    template_args = {
        page_flag: True,
        'staff_page': True,
        'last_updated': last_updated,
        'offices': offices_table,
        'summary': summary,
        'headline': headline,
        'elections': Election.objects.all(),
        'selected_election': election,
    }
    return render(request, 'vr_dashboard/election_day.html', template_args)


@user_passes_test(lambda user: user.is_staff)
def election_day_preliminary(request):
    page_flag = 'election_day_preliminary_votes_page'

    election = get_chosen_election(request)
    if election is None:
        return handle_invalid_election(request, page_flag)
    metadata, offices_table, country_table = \
        retrieve_report([election_key(ELECTION_DAY_METADATA_KEY, election),
                         election_key(ELECTION_DAY_OFFICES_TABLE_KEY, election),
                         election_key(ELECTION_DAY_BY_COUNTRY_KEY, election)])
    if metadata is None:
        return handle_missing_election_report(request, election, page_flag)

    last_updated = parse_iso_datetime(metadata['last_updated'])
    last_updated_msg = get_last_updated_msg(last_updated)

    country_name = list(country_table.keys())[0]
    country_prelim_counts = country_table[country_name].get(PRELIMINARY_VOTE_COUNTS, dict())

    # If this is for an old election prior to preliminary vote counts, or no
    # such counts have been received yet, generate a simple message instead
    # of tables of nothing.
    if not country_prelim_counts:
        return render(request, 'vr_dashboard/polling_error.html', {
            'heading': _("No Data Available"),
            'error_msg': _("Preliminary vote reports have not been received for this election."),
            'request': request,
            'elections': Election.objects.all(),
            'selected_election': election,
            page_flag: True,
            'staff_page': True,
        })

    template_args = {
        page_flag: True,
        'staff_page': True,
        # Any vote options that had no votes anywhere (yet) won't show up at
        # the country-wide aggregation and thus won't appear in the table.
        'vote_options': sorted(country_prelim_counts.keys()),
        'country_name': country_name,
        'country_prelim_counts': country_prelim_counts,
        'offices': offices_table,
        'last_updated': last_updated,
        'last_updated_msg': last_updated_msg,
        'elections': Election.objects.all(),
        'selected_election': election,
    }
    return render(request, 'vr_dashboard/election_day_preliminary.html', template_args)


@user_passes_test(lambda user: user.is_staff)
def election_day_center(request):
    response_format = get_response_format(request)
    if not response_format:  # requested format invalid
        return get_invalid_format_error(request)
    page_flag = 'election_day_center_page'
    election = get_chosen_election(request)
    if election is None:
        return handle_invalid_election(request, page_flag)
    metadata, polling_centers_table = \
        retrieve_report([election_key(ELECTION_DAY_METADATA_KEY, election),
                         election_key(ELECTION_DAY_POLLING_CENTERS_TABLE_KEY, election)])
    if metadata is None:
        return handle_missing_election_report(request, election, page_flag)

    last_updated = parse_iso_datetime(metadata['last_updated'])
    last_updated_msg = get_last_updated_msg(last_updated)

    if response_format == 'csv':
        response = HttpResponse(content_type='application/octet-stream', charset='utf-16le')
        client_filename = get_csv_filename(request, 'election_day_centers')
        response['Content-Disposition'] = 'attachment; filename="%s"' % client_filename
        w = get_csv_writer(response)
        w.writerow([
            _('Election Day Centers')
        ])
        w.writerow([
            last_updated_msg
        ])
        w.writerow([
            _('Polling Center'),
            _('Code'),
            _('Copied Polling Center'),
            _('Total Registrations'),
            _('Office'),
            _('Active'),
            _('Opened'),
            _('Reported Period') + ' 1',
            _('Reported Period') + ' 2',
            _('Reported Period') + ' 3',
            _('Reported Period') + ' 4',
            _('Closed')
        ])
        for center in polling_centers_table:
            closed = pgettext(center['closed'][0], center['closed'][1])
            active = _('No') if INACTIVE_FOR_ELECTION in center else _('Yes')
            w.writerow([
                center['name'],  # no English name available
                str(center['polling_center_code']),
                str(center[POLLING_CENTER_COPY_OF]) if POLLING_CENTER_COPY_OF in center else '',
                '' if POLLING_CENTER_COPY_OF in center else str(center['registration_count']),
                str(center['office_id']),
                active,
                center.get('opened', ''),
                str(center.get('votes_reported_1', '')),
                str(center.get('votes_reported_2', '')),
                str(center.get('votes_reported_3', '')),
                str(center.get('votes_reported_4', '')),
                closed])
        return response

    # Build the table manually; simply including polling_centers_table in the
    # template context eats a lot of CPU, seemingly just to process the data
    # in the table while building the context.

    center_url_template = str(reverse('vr_dashboard:election-day-center-n',
                                      kwargs={'center_id': UNUSED_CENTER_ID}))
    rows = []
    for center in polling_centers_table:
        center_url = center_url_template.replace(str(UNUSED_CENTER_ID),
                                                 str(center['polling_center_code']))

        # For copy centers, '' is used instead of something like 'N/A' to maintain sort-ability.
        # TBD: Is that actually required now that the sort is customized?
        if POLLING_CENTER_COPY_OF in center:
            registrations = ''
        else:
            registrations = center['registration_count']
        active = _('No') if INACTIVE_FOR_ELECTION in center else _('Yes')
        center_name = center['name']  # no English name available
        closed = pgettext(center['closed'][0], center['closed'][1])

        # Important: This text will be included in the HTML table without
        #            escaping.  The string fields were built by the
        #            reporting_api app and stored in Redis.
        row = """<tr>
  <td><a href='%s'>%s</a></td>
  <td>%d</td>
  <td>%s</td>
  <td>%s</td>
  <td>%d</td>
  <td>%s</td>
  <td>%s</td>
  <td>%s</td>
  <td>%s</td>
  <td>%s</td>
  <td>%s</td>
  <td>%s</td>
</tr>""" % (center_url, center_name,
            center['polling_center_code'],
            center[POLLING_CENTER_COPY_OF] if POLLING_CENTER_COPY_OF in center else '',
            intcomma(registrations) if registrations else '',
            center['office_id'], active, center.get('opened', ''),
            intcomma_if(center, 'votes_reported_1'), intcomma_if(center, 'votes_reported_2'),
            intcomma_if(center, 'votes_reported_3'), intcomma_if(center, 'votes_reported_4'),
            closed)
        rows.append(row)

    template_args = {
        page_flag: True,
        'staff_page': True,
        'centers': '\n'.join(rows),
        'last_updated': last_updated,
        'elections': Election.objects.all(),
        'selected_election': election,
    }
    return render(request, 'vr_dashboard/election_day_center.html', template_args)


db_timestamp_matcher = re.compile('(.*)([+-][0-9]{2,4})')


def parse_db_timestamp(s):
    """ Return TZ-aware datetime from a string of form
                %Y-%m-%d %H:%M:%S%z where %z is '+' or '-' then HH[MM]
        If the TZ offset substring is anything but "+00", log an error and act
        as if it had been "+00".  Bad examples: "-05", "+02", etc.
    """
    m = db_timestamp_matcher.match(s)
    assert m, 'Failed to parse "%s"' % s
    timestamp, offset = m.group(1), m.group(2)
    if offset != '+00':
        logger.error('Unexpected UTC offset "%s" in timestamp "%s"' % (offset, s))

    timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
    return timestamp.replace(tzinfo=utc)


phone_number_field_matcher = re.compile('([0-9]+) ([XW]) (.*)')


def parse_phone_number_fields(s):
    """ Given a center phone description from the ED report, parse it into
    presentation fields.

    The string description has phone number, whitelist indicator, and timestamp
    in the following formats:

        u'218922787062 X <ignored-timestamp>'
        u'218922787062 W <whitelist-timestamp>'
    """
    m = phone_number_field_matcher.match(s)
    assert m, 'Failed to parse "%s"' % s
    phone = m.group(1)
    flag = m.group(2)
    timestamp = parse_db_timestamp(m.group(3)).strftime('%m/%d %H:%M') if flag == 'W' else ''
    return {
        'number': format_phone_number(phone),
        'flag': flag if flag == 'X' else '',
        'error': _('Not Whitelisted') if flag == 'X' else '',
        'timestamp': timestamp
    }


@user_passes_test(lambda user: user.is_staff)
def election_day_center_n(request, center_id):
    center_id = int(center_id)
    page_flag = 'election_day_overview_page'
    election = get_chosen_election(request)
    if election is None:
        return handle_invalid_election(request, page_flag)
    center_table_key = election_day_polling_center_table_key(election, center_id)
    metadata, all_centers, center = \
        retrieve_report([election_key(ELECTION_DAY_METADATA_KEY, election),
                         election_key(ELECTION_DAY_POLLING_CENTERS_TABLE_KEY, election),
                         center_table_key])
    if metadata is None:  # first is None => some key wasn't found
        # See if the center report wasn't returned because we don't have data on it.
        # (If all_centers is None, the report is missing from Redis.)
        if center is None and all_centers:
            # un-JSON skipped on retrieve_report failure
            all_centers = json.loads(all_centers.decode())
            if center_id not in [c[POLLING_CENTER_CODE] for c in all_centers]:
                logger.warning('URL contains unrecognized center id')
                args = {
                    'error_msg': _("Center id %s is not valid.") % center_id,
                    page_flag: True,
                    'staff_page': True,
                }
                return render(request, 'vr_dashboard/polling_error.html', args, status=404)

        return handle_missing_election_report(request, election, page_flag)

    # Grab the center log separately, as it is commonly missing (center not used for
    # election or center hasn't yet sent messages).
    center_log = retrieve_report(election_day_polling_center_log_key(election, center_id))
    if center_log is None:  # assume center sent no messages
        center_log = []

    if POLLING_CENTER_COPY_OF in center:
        registrations = _('N/A')
    else:
        registrations = intcomma_if(center, 'registration_count')
    stats = {'last_opened': center.get('last_opened', _('Not Opened')),
             'reported_period_1': emphasized_data(intcomma_if(center, 'votes_reported_1')),
             'reported_period_2': emphasized_data(intcomma_if(center, 'votes_reported_2')),
             'reported_period_3': emphasized_data(intcomma_if(center, 'votes_reported_3')),
             'reported_period_4': emphasized_data(intcomma_if(center, 'votes_reported_4')),
             'total': emphasized_data(registrations),
             }
    phones = [parse_phone_number_fields(number) for number in sorted(center['phones']) if number]
    last_updated = parse_iso_datetime(metadata['last_updated'])
    checkin_start, ignored = center_checkin_times(election)
    center_log = [message for message in center_log
                  if parse_iso_datetime(message['creation_date']) >= checkin_start]
    center_log = sorted(center_log, key=lambda e: e['creation_date'])
    stats['last_report'] = _('Not Reported')
    for message in center_log:
        if message['type'] == 'votesreport':
            message['period'], message['votes'] = message['data'].split(',')
            message['type'] = _('Votes Report')
        elif message['type'] == 'phonelink':
            message['type'] = _('Phone Link')
        elif message['type'] == 'rollcall':
            message['type'] = _('Check in')
        elif message['type'] == 'dailyreport':
            message['type'] = _('Daily Report')
        if message['phone_number']:
            message['phone_number'] = format_phone_number(message['phone_number'])
        message['creation_date'] = \
            printable_iso_datetime(message['creation_date'])
        stats['last_report'] = message['creation_date']

    copies = []
    if POLLING_CENTER_COPY_OF not in center:
        # maybe this non-copy center has copies
        for maybe_copy in all_centers:
            if maybe_copy.get(POLLING_CENTER_COPY_OF, None) == center_id:
                copies.append(maybe_copy['polling_center_code'])

    template_args = {
        page_flag: True,
        'staff_page': True,
        'center': center,
        'center_id': center_id,
        'copies': copies,
        'last_updated': last_updated,
        'stats': stats,
        'phones': phones,
        'log': center_log,
        'elections': Election.objects.all(),
        'selected_election': election,
    }
    return render(request, 'vr_dashboard/election_day_center_n.html', template_args)


@user_passes_test(lambda user: user.is_staff)
def election_day_office_n(request, office_id):
    response_format = get_response_format(request)
    if not response_format:  # requested format invalid
        return get_invalid_format_error(request)
    office_id = int(office_id)
    page_flag = 'election_day_overview_page'
    election = get_chosen_election(request)
    if election is None:
        return handle_invalid_election(request, page_flag)
    metadata, office_table, polling_centers_table = \
        retrieve_report([election_key(ELECTION_DAY_METADATA_KEY, election),
                         election_key(ELECTION_DAY_OFFICES_TABLE_KEY, election),
                         election_key(ELECTION_DAY_POLLING_CENTERS_TABLE_KEY, election)])
    if metadata is None:
        return handle_missing_election_report(request, election, page_flag)

    last_updated = parse_iso_datetime(metadata['last_updated'])
    last_updated_msg = get_last_updated_msg(last_updated)

    # Grab just the slice of office_table needed here.  (The entire table isn't huge, so
    # it is not broken down by office in Redis.)
    office_in_list = [office for office in office_table if office['office_id'] == office_id]

    if not office_in_list:  # invalid office id
        logger.warning('URL contains unrecognized office id')
        args = {
            'error_msg': _("Office id %s is not valid.") % office_id,
            page_flag: True,
            'staff_page': True,
        }
        return render(request, 'vr_dashboard/polling_error.html', args, status=404)

    assert len(office_in_list) == 1, 'Office %d is in table more than once' % office_id
    office = office_in_list[0]
    if request.LANGUAGE_CODE == 'ar':
        office_name = office['arabic_name']
    else:
        office_name = office['english_name']

    office_centers_table = []
    centers_in_office = metadata['centers_by_office'][str(office_id)]

    periods = ['reported_period_%d' % i for i in range(1, 5)]
    for center_id in centers_in_office:
        center = [entry for entry in polling_centers_table
                  if entry['polling_center_code'] == center_id][0]
        center['missing_period'] = False
        for period in periods:
            if center[period] == 'has_not_reported':
                center['missing_period'] = True
        office_centers_table.append(center)

    total_reported_1 = 0
    total_reported_2 = 0
    total_reported_3 = 0
    total_reported_4 = 0

    translated_column_vals = {'has_reported': pgettext('has_reported', 'Yes'),
                              'has_not_reported': pgettext('has_not_reported', 'No'),
                              'no_data': '-',
                              'not_due': ''
                              }
    for center in office_centers_table:
        total_reported_1 += center.get('votes_reported_1', 0)
        total_reported_2 += center.get('votes_reported_2', 0)
        total_reported_3 += center.get('votes_reported_3', 0)
        total_reported_4 += center.get('votes_reported_4', 0)

        for period in ['1', '2', '3', '4']:
            val = center['reported_period_' + period]
            center['reported_period_' + period + '_printable'] = translated_column_vals[val]
            if val == 'has_not_reported':
                center['tr_class'] = 'missing_period'  # highlight entire row

        if INACTIVE_FOR_ELECTION in center:
            center['tr_class'] = 'inactive_for_election'

    if response_format == 'csv':
        response = HttpResponse(content_type='application/octet-stream', charset='utf-16le')
        client_filename = get_csv_filename(request, 'election_day_office_%d' % office_id)
        response['Content-Disposition'] = 'attachment; filename="%s"' % client_filename
        w = get_csv_writer(response)
        w.writerow([
            _('Election Day Office %d' % office_id)
        ])
        w.writerow([
            last_updated_msg
        ])
        w.writerow([
            _('Polling Center'),
            _('Code'),
            _('Active'),
            _('Opened'),
            _('Reported Period') + ' 1',
            _('Reported Period') + ' 2',
            _('Reported Period') + ' 3',
            _('Reported Period') + ' 4'
        ])
        for row in office_centers_table:
            active = _('No') if INACTIVE_FOR_ELECTION in row else _('Yes')
            w.writerow([
                row['name'],
                str(row['polling_center_code']),
                active,
                row.get('opened_today') or '-',
                row['reported_period_1_printable'],
                row['reported_period_2_printable'],
                row['reported_period_3_printable'],
                row['reported_period_4_printable']
            ])
        return response

    inactive_centers = office[INACTIVE_FOR_ELECTION] if INACTIVE_FOR_ELECTION in office else []

    headline = \
        {'as_of_datetime':
         _("As of {time} on {date}:").format(time=last_updated.strftime('%H:%M'),
                                             date=last_updated.strftime('%d/%m')),
         'open_centers':
         _("{count} centers have opened").format(count=emphasized_data(intcomma(office['opened']))),

         'unopen_centers':
         _("{count} centers have not opened").format(
             count=emphasized_data(intcomma(office['not_opened']))),

         'inactive_centers':
         _("{count} are inactive").format(
             count=emphasized_data(intcomma(len(inactive_centers)))
         ),

         'period1': PERIOD_VOTES_REPORTED_MESSAGE.format(
             count=emphasized_data(intcomma(total_reported_1)), period=1),

         'period2': PERIOD_VOTES_REPORTED_MESSAGE.format(
             count=emphasized_data(intcomma(total_reported_2)), period=2),

         'period3': PERIOD_VOTES_REPORTED_MESSAGE.format(
             count=emphasized_data(intcomma(total_reported_3)), period=3),

         'period4': PERIOD_VOTES_REPORTED_MESSAGE.format(
             count=emphasized_data(intcomma(total_reported_4)), period=4)
         }

    last_updated = parse_iso_datetime(metadata['last_updated'])
    template_args = {
        page_flag: True,
        'staff_page': True,
        'office_id': office_id,
        'office_name': office_name,
        'last_updated': last_updated,
        'headline': headline,
        'office_centers_table': office_centers_table,
        'elections': Election.objects.all(),
        'selected_election': election,
    }
    return render(request, 'vr_dashboard/election_day_office_n.html', template_args)


@user_passes_test(lambda user: user.is_staff)
def election_day_hq(request):
    """Implement the election day HQ view"""
    page_flag = 'election_day_hq_page'
    election = get_chosen_election(request)
    if election is None:
        return handle_invalid_election(request, page_flag)
    metadata, reports = retrieve_report([election_key(ELECTION_DAY_METADATA_KEY, election),
                                         election_key(ELECTION_DAY_HQ_REPORTS_KEY, election)])
    if metadata is None:
        return handle_missing_election_report(request, election, page_flag)

    last_updated = parse_iso_datetime(metadata['last_updated'])

    # The reports were simplified to support JSON serialization -- int keys
    # were stringified, Office objects were omitted, and the ordering of the
    # dictionaries was lost.  Restore those properties.
    offices_by_id = {office.id: office for office in Office.objects.all()}
    report_types = [report_type for report_type in reports.keys() if report_type != 'national']
    for report_type in report_types:
        new_report = OrderedDict()
        if report_type == 'by_office':
            transform_key = lambda k: offices_by_id[k]
        else:
            transform_key = lambda k: k
        for key in sorted([int(key) for key in reports[report_type].keys()]):
            new_report[transform_key(key)] = reports[report_type][str(key)]
        reports[report_type] = new_report
    template_args = {
        'result': reports,
        'region_names': Office.REGION_NAMES,
        'center_type_names': RegistrationCenter.Types.NAMES[request.LANGUAGE_CODE],
        page_flag: True,
        'staff_page': True,
        'last_updated': last_updated,
        'elections': Election.objects.all(),
        'selected_election': election,
    }
    return render(request, 'vr_dashboard/hq.html', template_args)
