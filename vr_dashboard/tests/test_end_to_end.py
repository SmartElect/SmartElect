import base64
from copy import deepcopy
from datetime import datetime, timedelta
import logging
import re
from StringIO import StringIO

from django.conf import settings
from django.core.urlresolvers import reverse
from django.test import TestCase
from mock import patch
from pytz import timezone
from civil_registry.tests.factories import CitizenFactory

from libya_elections.constants import MESSAGE_1, INCOMING
from libya_elections.csv_utils import UnicodeReader
from libya_elections.utils import astz
from libya_site.tests.factories import DEFAULT_USER_PASSWORD, UserFactory
from libya_site.utils import intcomma
from polling_reports.models import CenterClosedForElection, CenterOpen, PollingReport, \
    PreliminaryVoteCount
from register.models import Registration, SMS
from register.tests.base import FUTURE_DAY
from register.tests.factories import BackendFactory, RegistrationCenterFactory
from reporting_api.constants import PRELIMINARY_VOTE_COUNTS
from reporting_api.create_test_data import STAFF_PHONE_NUMBER_PATTERN
from reporting_api import reports
from reporting_api.reports import calc_yesterday
from reporting_api.tests import test_reports
from reporting_api.views import REPORT_USER_DB
from reporting_api import tasks
from voting.tests.factories import ElectionFactory


logger = logging.getLogger(__name__)

# Not all of these are actually modified, so defaultdict(int) won't work
# without more logic.
EMPTY_SUMMARY = {
    'opened': 0,
    'unopened': 0,
    'votes_reported_1': 0,
    'votes_reported_2': 0,
    'votes_reported_3': 0,
    'votes_reported_4': 0,
    'inactive': 0,
}


class TestEndToEnd(TestCase):

    def setUp(self):
        self.staff_user = UserFactory()
        self.staff_user.is_staff = True
        self.staff_user.save()
        assert self.client.login(username=self.staff_user.username, password=DEFAULT_USER_PASSWORD)
        self.reporting_user = test_reports.TEST_USERNAME
        self.reporting_password = test_reports.TEST_PASSWORD
        REPORT_USER_DB[self.reporting_user] = self.reporting_password
        # Pick a start time that represents different days in Libya vs UTC
        tz = timezone(settings.TIME_ZONE)
        polling_start_time = astz(FUTURE_DAY.replace(hour=22), tz)
        polling_end_time = tz.normalize(polling_start_time + timedelta(hours=16))
        self.election = ElectionFactory(
            polling_start_time=polling_start_time,
            polling_end_time=polling_end_time,
        )
        self.election_day_dt = self.election.polling_start_time
        # Create "decoy" election just to confirm that it doesn't break reports.
        decoy_start_time = tz.normalize(polling_start_time - timedelta(days=10))
        decoy_end_time = tz.normalize(decoy_start_time + timedelta(hours=16))
        ElectionFactory(
            polling_start_time=decoy_start_time,
            polling_end_time=decoy_end_time,
        )
        self.all_centers = []
        self.rc_1 = RegistrationCenterFactory()
        self.all_centers.append(self.rc_1)
        self.rc_2 = RegistrationCenterFactory()
        self.all_centers.append(self.rc_2)
        self.rc_3 = RegistrationCenterFactory()
        self.all_centers.append(self.rc_3)
        self.rc_4 = RegistrationCenterFactory()
        self.all_centers.append(self.rc_4)
        self.copy_of_rc_1 = RegistrationCenterFactory(copy_of=self.rc_1, office=self.rc_1.office)
        self.all_centers.append(self.copy_of_rc_1)
        # rc_5 is inactive for this election
        self.rc_5 = RegistrationCenterFactory(office=self.rc_1.office)
        self.all_centers.append(self.rc_5)
        inactive_on_election = CenterClosedForElection(
            registration_center=self.rc_5, election=self.election
        )
        inactive_on_election.full_clean()
        inactive_on_election.save()
        self.all_office_ids = [center.office_id for center in self.all_centers]
        self.carrier_1 = BackendFactory()
        self.citizen_1 = CitizenFactory()

        # Create registrations on the 4 days leading up to election day
        # Put the registrations at different hours of the day to stress TZ handling.
        self.registration_dates = []
        self.registration_date_strs = []
        hour_of_day = 0
        for delta_days in range(10, 4, -1):
            assert hour_of_day < 24
            reg_date = astz(self.election_day_dt - timedelta(days=delta_days), tz)\
                .replace(hour=hour_of_day)
            hour_of_day += 4
            self.registration_dates.append(reg_date)
            self.registration_date_strs.append(reg_date.strftime('%Y-%m-%d'))
        self.yesterday_date, _ = calc_yesterday(self.registration_date_strs)
        self.yesterday_date_dm = self.yesterday_date.strftime('%d/%m')
        # yesterday_date is a date; get a datetime form
        self.yesterday_date_dt = tz.localize(datetime(self.yesterday_date.year,
                                                      self.yesterday_date.month,
                                                      self.yesterday_date.day,
                                                      0, 0, 0))
        self.staff_phone_number = STAFF_PHONE_NUMBER_PATTERN % 12345

    def _describe_infra(self):
        logger.info("Registration Centers:")
        for center in self.all_centers:
            logger.info('  %s' % center)
            logger.info('    office id %d' % center.office.id)
            if center.copy_of:
                logger.info('    copy of center %d' % center.center_id)

    def _request(self, url, **extra):
        """ Request the specified URL using self.client, perform any common
        processing like checking the status code and logging the response.
        """
        logger.info(url)
        if extra:
            logger.info(extra)
        rsp = self.client.get(url, **extra)
        self.assertEqual(200, rsp.status_code)
        logger.info(rsp.content)
        return rsp

    def _request_csv(self, url, **extra):
        """ Like _request() above, but also parse the response body as a CSV
        as created by the voter registration dashboard and log in parsed form.

        This adds the query arg which specifies CSV rendering.
        """
        url += '?format=csv'
        rsp = self._request(url, **extra)
        content = rsp.content[2:]  # skip BOM
        reader = UnicodeReader(StringIO(content), encoding="utf-16-le", delimiter='\t')
        rows = []
        for row in reader:
            rows.append(row)
            logger.info(row)
        return rows

    def _msg_type_to_str(self, t):
        """ Get string form of the provided SMS message type.
        """
        # unicode() resolves the lazy translation object
        return unicode([x for x in SMS.MESSAGE_TYPES if x[0] == t][0][1])

    def _create_registrations(self, expected_stats):
        """ Create different numbers of registrations on each of the chosen registration dates
        so we can be sure that a count was assigned to the correct date.
        """
        msg_type_str = self._msg_type_to_str(SMS.REGISTRATION)
        expected_stats['message_stats'][msg_type_str] = dict()
        # Accumulators for by-center and total number of registrations
        expected_stats['by_center'][self.rc_1.center_id]['registrations'] = 0
        expected_stats['by_center'][self.rc_2.center_id]['registrations'] = 0
        expected_stats['by_center'][self.rc_3.center_id]['registrations'] = 0
        expected_stats['by_center'][self.rc_4.center_id]['registrations'] = 0
        expected_stats['by_center'][self.copy_of_rc_1.center_id]['registrations'] = ''
        expected_stats['by_center'][self.rc_5.center_id]['registrations'] = 0
        expected_stats['message_stats'][msg_type_str]['total'] = 0
        for i, reg_date in enumerate(self.registration_dates):
            regs_on_date = i + 1
            for j in range(regs_on_date):
                citizen = CitizenFactory()
                s = SMS(from_number='12345', to_number='12345', citizen=citizen,
                        direction=INCOMING, message='my reg message',
                        msg_type=SMS.REGISTRATION, message_code=MESSAGE_1,
                        carrier=self.carrier_1, creation_date=reg_date)
                s.full_clean()
                s.save()
                r = Registration(citizen=citizen, registration_center=self.rc_1,
                                 archive_time=None,
                                 sms=s, creation_date=reg_date, modification_date=reg_date)
                r.full_clean()
                r.save()
                expected_stats['by_center'][self.rc_1.center_id]['registrations'] += 1
            expected_stats['message_stats'][msg_type_str]['total'] += regs_on_date
            # Capture the count on "yesterday" (reported on SMS page)
            if self.yesterday_date == reg_date.date():
                expected_stats['message_stats'][msg_type_str][self.yesterday_date_dm] = \
                    regs_on_date

    @classmethod
    def _max_report_time(cls, time1, time2):
        """ Return the greater of the two times.  time1 can be None, which
        means long, long ago.
        """
        return max(time1 or time2, time2)

    def _create_election_day_data(self, expected_stats):
        """Create various types of election data for testing of the election
        day dashboard."""

        # Pick open times that could vary by date based on time zone.
        rc_1_open_time = self.election_day_dt.replace(hour=1, minute=23)
        rc_2_open_time = self.election_day_dt.replace(hour=10, minute=23)
        # This center open time is before the election time really starts,
        # so it will be reported under the corresponding office as an
        # unopened center.
        open_time_3 = self.election.start_time - timedelta(hours=6)

        # configure election day activities by registration center
        center_activities = []

        center_activities.append({
            'center': self.rc_1,
            'open_time': rc_1_open_time,
            'phone_number': STAFF_PHONE_NUMBER_PATTERN % 1,
        })

        center_activities.append({
            'center': self.rc_2,
            'open_time': rc_2_open_time,
            'phone_number': STAFF_PHONE_NUMBER_PATTERN % 1,
            'prelim_time': self.election_day_dt,
            'prelim_option': 9,
            'prelim_votes': 7312,  # four digits to test intcomma formatting
            'period_4_time': rc_2_open_time + timedelta(hours=6),
            'period_4_count': 79,
            # period "5" is a report for period 4 sent on following day
            'period_5_time': self.election_day_dt + timedelta(days=1),
            'period_5_count': 82,
        })

        center_activities.append({
            'center': self.rc_3,
            'open_time': open_time_3,
            'phone_number': STAFF_PHONE_NUMBER_PATTERN % 2,
        })

        center_activities.append({
            'center': self.rc_4,
            # DOES NOT SEND CenterOpen or anything else
        })

        center_activities.append({
            'center': self.copy_of_rc_1,
            # The copy center opened, coincidentally at the same time as the copied center.
            'open_time': rc_1_open_time,
            'phone_number': STAFF_PHONE_NUMBER_PATTERN % 3,
            # vote report for period 2
            'period_2_time': self.election_day_dt,
            'period_2_count': 4321,  # four digits to test intcomma formatting
        })

        center_activities.append({
            'center': self.rc_5,
            # DOES NOT SEND CenterOpen or anything else
            # This shares an office id with rc_1, and is also marked as
            # inactive for this particular election.
        })

        # shortcuts into dictionaries
        expected_center_stats = expected_stats['by_center']
        expected_office_stats = expected_stats['by_office']
        expected_summary_stats = expected_stats['summary']

        # Clear office-level summaries
        # (Some offices will be repeated, but it doesn't matter.)
        for activity in center_activities:
            office_id = activity['center'].office_id
            for key in ('opened', 'closed', 'not_reported_1', 'not_reported_2', 'not_reported_3',
                        'not_reported_4', 'unopened'):
                expected_office_stats[office_id][key] = 0
            expected_office_stats[office_id]['summary'] = deepcopy(EMPTY_SUMMARY)

        # Create the messages, increment/set counters/fields to represent
        # expected dashboard data.
        for activity in center_activities:
            # shortcuts specific to this center
            expected_for_this_center = expected_center_stats[activity['center'].center_id]
            expected_for_this_office = expected_office_stats[activity['center'].office_id]
            expected_summary_for_this_office = expected_for_this_office['summary']

            last_report_dt = None  # track the last report from this center

            open_time = activity.get('open_time', None)
            if open_time:
                open_msg = CenterOpen(election=self.election,
                                      phone_number=activity['phone_number'],
                                      registration_center=activity['center'],
                                      creation_date=activity['open_time'])
                open_msg.full_clean()
                open_msg.save()
                last_report_dt = self._max_report_time(last_report_dt, activity['open_time'])

            # It does not count as an open if it happened too early
            if open_time and open_time >= self.election.start_time:
                expected_for_this_center['ed_open'] = open_time.strftime('%d/%m %H:%M')
                expected_for_this_center['opened_hm'] = open_time.strftime('%H:%M')
                expected_for_this_office['opened'] += 1
                expected_summary_stats['opened'] += 1
                expected_summary_for_this_office['opened'] += 1
            else:
                expected_for_this_center['ed_open'] = None
                expected_for_this_center['opened_hm'] = None
                expected_for_this_office['unopened'] += 1
                expected_summary_stats['unopened'] += 1
                expected_summary_for_this_office['unopened'] += 1

            for period in ('1', '2', '3', '4'):
                report_time, report_count = \
                    activity.get('period_' + period + '_time', None), \
                    activity.get('period_' + period + '_count', None)

                if report_time:
                    r = PollingReport(election=self.election,
                                      phone_number=activity['phone_number'],
                                      registration_center=activity['center'],
                                      period_number=int(period),
                                      num_voters=report_count,
                                      creation_date=report_time)
                    r.full_clean()
                    r.save()
                    last_report_dt = self._max_report_time(last_report_dt, report_time)

                    expected_for_this_center['votes_reported_' + period] = report_count
                    expected_for_this_center['reported_period_' + period] = 'has_reported'
                    expected_for_this_center['reported_period_' + period + '_count'] = report_count
                    expected_for_this_office['votes_reported_' + period] = report_count
                    expected_summary_stats['votes_reported_' + period] += report_count
                    expected_summary_for_this_office['votes_reported_' + period] += report_count
                    if period == '4':  # got period 4 report, so didn't close
                        expected_for_this_center['is_closed'] = 'Yes'
                        expected_for_this_office['closed'] += 1
                else:
                    if open_time and open_time >= self.election.start_time:
                        # The effective time of the reports was just after period 2, so
                        # if this is the period 1 or 2 report then it is overdue, and
                        # if this is the period 3 or 4 report then it is not due yet.
                        flag = 'has_not_reported' if period in ('1', '2') else 'not_due'
                        expected_for_this_center['reported_period_' + period] = flag
                    else:
                        expected_for_this_center['reported_period_' + period] = 'no_data'
                    expected_for_this_center['reported_period_' + period + '_count'] = 0
                    expected_for_this_office['not_reported_' + period] += 1
                    if period == '4':  # no period 4 report, so didn't close
                        expected_for_this_center['is_closed'] = 'No'

            # Very basic support for sending period 4 report on day after election
            #
            # It assumes that a period 4 report was also sent on election day, which
            # simplifies handling of votes_reported_4 counters and information on
            # closing.
            #
            # Period "5" is period 4 on the following day.
            period_5_time = activity.get('period_5_time', None)
            if period_5_time:
                period_5_count = activity['period_5_count']
                period_4_count = activity['period_4_count']

                r = PollingReport(election=self.election,
                                  phone_number=activity['phone_number'],
                                  registration_center=activity['center'],
                                  period_number=4,
                                  num_voters=period_5_count,
                                  creation_date=period_5_time)
                r.full_clean()
                r.save()
                last_report_dt = self._max_report_time(last_report_dt, period_5_time)

                # Add in delta to prior period 4 report
                delta = period_5_count - period_4_count
                expected_for_this_center['votes_reported_4'] += delta
                expected_for_this_center['reported_period_4_count'] += delta
                expected_for_this_office['votes_reported_4'] += delta
                expected_summary_stats['votes_reported_4'] += delta
                expected_summary_for_this_office['votes_reported_4'] += delta

            prelim_time = activity.get('prelim_time', None)
            if prelim_time:
                prelim = PreliminaryVoteCount(election=self.election,
                                              phone_number=activity['phone_number'],
                                              registration_center=activity['center'],
                                              option=activity['prelim_option'],
                                              num_votes=activity['prelim_votes'],
                                              creation_date=prelim_time)
                prelim.full_clean()
                prelim.save()
                last_report_dt = self._max_report_time(last_report_dt, prelim_time)

                expected_for_this_office['prelim'] = {
                    str(activity['prelim_option']): intcomma(activity['prelim_votes'])
                }

            expected_for_this_center['last_report'] = \
                'Not Reported' if not last_report_dt else \
                last_report_dt.strftime('%d/%m %H:%M')

        # rc_5 is inactive for this election
        # (CenterClosedForElection created when center was created)
        # Now that the office 'summary' has been set up, note where inactive should show up.
        expected_center_stats[self.rc_5.center_id]['inactive'] = True
        expected_office_stats[self.rc_5.office.id]['summary']['inactive'] += 1

    def _create_sms_messages(self, expected_stats):
        """ Create SMS messages of a certain type at different times "yesterday".
        The times should have the same date in local TZ but different dates when
        the TZ is bungled somewhere.  By making them "yesterday", the counts will show
        up in the SMS page in the yesterday column.
        """
        msg_type = SMS.INVALID_CENTRE_CODE_LENGTH
        msg_type_str = self._msg_type_to_str(msg_type)
        expected_stats['message_stats'][msg_type_str] = dict()
        num_staff_messages = 8
        for msg_hour in range(num_staff_messages):
            msg_time = self.yesterday_date_dt.replace(hour=msg_hour, minute=23)
            s = SMS(from_number=self.staff_phone_number, to_number='12345', citizen=self.citizen_1,
                    direction=INCOMING, message='my message',
                    msg_type=msg_type, message_code=MESSAGE_1,
                    carrier=self.carrier_1, creation_date=msg_time)
            s.full_clean()
            s.save()
        expected_stats['message_stats'][msg_type_str][self.yesterday_date_dt.strftime('%d/%m')] = \
            num_staff_messages
        expected_stats['message_stats'][msg_type_str]['total'] = num_staff_messages
        expected_stats['phone_history'][self.staff_phone_number] = {
            'message_count': num_staff_messages,
        }

    @classmethod
    def _str_to_int(cls, s):
        """ Convert the input numeric string, which may contain comma
        separators, to an int.
        """
        return int(s.replace(',', ''))

    @classmethod
    def _extract_int_from_span(cls, s):
        """Input s contains a number we need to convert to an int, embedded
        in a <span...></span>."""
        m = re.search('<span.*>(.+)</span>', s)
        if m:
            return cls._str_to_int(m.group(1))
        else:
            raise ValueError('Argument "%" does not contain <span></span>')

    def _parse_headline(self, headline, has_inactive=False):
        return {
            # Grab the number from u'3 centers have opened' and similar for unopened and inactive
            'opened': self._extract_int_from_span(headline['open_centers']),
            'unopened': self._extract_int_from_span(headline['unopen_centers']),
            'inactive':
                self._extract_int_from_span(headline['inactive_centers']) if has_inactive else 0,
            # Grab the number from u'Votes reported period 1: 0'
            'votes_reported_1': self._extract_int_from_span(headline['period1']),
            'votes_reported_2': self._extract_int_from_span(headline['period2']),
            'votes_reported_3': self._extract_int_from_span(headline['period3']),
            'votes_reported_4': self._extract_int_from_span(headline['period4']),
        }

    def _read_dashboard(self, actual_stats):
        """ Read parts of the dashboard that contain data we're testing and fill in the
        provided dictionary with the stats we observe.

        This only supports a small subset of the stats on the dashboard.
        """

        # Process the office-specific election day screen
        for office_id in self.all_office_ids:
            url = reverse('vr_dashboard:election-day-office-n', args=(office_id,))
            rsp = self._request(url)
            actual_stats['by_office'][office_id]['summary'] = \
                self._parse_headline(rsp.context['headline'], has_inactive=True)
            for row in rsp.context['office_centers_table']:
                center_id = row['polling_center_code']
                assert center_id in actual_stats['by_center'], \
                    'Center id %s is unexpected (not one of %s)' % \
                    (center_id, actual_stats['by_center'].keys())
                if 'opened_today' in row:
                    open_dt = row['opened_today']
                    actual_stats['by_center'][center_id]['ed_open'] = open_dt
                if 'inactive_for_election' in row:
                    actual_stats['by_center'][center_id]['inactive'] = True
                    self.assertEqual(row['tr_class'], 'inactive_for_election')
                for period in ['1', '2', '3', '4']:
                    votes_reported_period = 'votes_reported_' + period
                    if votes_reported_period in row:
                        actual_stats['by_center'][center_id][votes_reported_period] = \
                            row[votes_reported_period]
                        actual_stats['by_office'][office_id][votes_reported_period] = \
                            row[votes_reported_period]
                    actual_stats['by_center'][center_id]['reported_period_' + period] = \
                        row['reported_period_' + period]

        # prelim vote counts
        url = reverse('vr_dashboard:election-day-preliminary')
        rsp = self._request(url)
        for office in rsp.context['offices']:
            if PRELIMINARY_VOTE_COUNTS in office:
                actual_stats['by_office'][office['office_id']]['prelim'] = {
                    key: intcomma(value)
                    for key, value in office[PRELIMINARY_VOTE_COUNTS].iteritems()
                }

        # process the sms screen
        url = reverse('vr_dashboard:sms')
        rsp = self._request(url)
        yesterday_str = rsp.context['sms_stats']['last_date']
        for stats in rsp.context['message_stats_by_type']:
            msg_type = stats['translated_sms_type']
            msg_yesterday_count = int(stats['last'])
            msg_total_count = int(stats['total'])
            actual_stats['message_stats'][msg_type] = {
                yesterday_str: msg_yesterday_count,
                'total': msg_total_count
            }

        # look at summary stats from main election_day page
        url = reverse('vr_dashboard:election-day')
        rsp = self._request(url)
        actual_stats['summary'] = self._parse_headline(rsp.context['headline'])
        for row in rsp.context['offices']:
            actual_office_stats = actual_stats['by_office'][row['office_id']]
            actual_office_stats['opened'] = row['opened']
            actual_office_stats['unopened'] = row['not_opened']
            actual_office_stats['closed'] = row['closed']
            actual_office_stats['not_reported_1'] = row['not_reported_1']
            actual_office_stats['not_reported_2'] = row['not_reported_2']
            actual_office_stats['not_reported_3'] = row['not_reported_3']
            actual_office_stats['not_reported_4'] = row['not_reported_4']

        # process the election day CSVs, testing something from each data row
        csv = self._request_csv(reverse('vr_dashboard:election-day'))
        # office data starts in 4th row, country-wide is last row
        for row in csv[3:-1]:
            office_id = int(row[0].split()[0])
            opened = int(row[2])
            # already grabbed from normal view, so make sure it matches
            self.assertEquals(actual_stats['by_office'][office_id]['opened'], opened)

        csv = self._request_csv(reverse('vr_dashboard:election-day-center'))
        # center data starts in 4th row
        for row in csv[3:]:
            center_id = int(row[1])
            total_regs = '' if not row[3] else int(row[3])  # '' for copy center
            actual_stats['by_center'][center_id]['registrations'] = total_regs
            # inactive already read from election-day-office-n; make sure it matches
            active_flag = 'No' if 'inactive' in actual_stats['by_center'][center_id] else 'Yes'
            self.assertEqual(row[5], active_flag)
            actual_stats['by_center'][center_id]['opened_hm'] = row[6] if row[6] else None
            actual_stats['by_center'][center_id]['is_closed'] = row[11]
            # votes_reported_N already read from election-day-office-n; make sure it matches
            for period, where_in_row in (('1', 7), ('2', 8), ('3', 9), ('4', 10)):
                period_key = 'votes_reported_' + period
                if row[where_in_row]:
                    self.assertEquals(actual_stats['by_center'][center_id][period_key],
                                      int(row[where_in_row]))
                else:
                    self.assertNotIn(period_key, actual_stats['by_center'][center_id])

        for office_id in self.all_office_ids:
            csv = self._request_csv(reverse('vr_dashboard:election-day-office-n',
                                            args=[office_id]))
            # The center open time has already been read from the HTML, so just
            # make sure that it is consistent in the CSV.
            # Note that if there's no CenterOpen, the context will have None but
            # the screen and CSV will have '-'.
            center_id = int(csv[3][1])
            open_dt = csv[3][3]
            self.assertEqual(
                actual_stats['by_center'][center_id]['ed_open'] or '-',
                open_dt,
                'Open for center %d different between HTML and CSV (%s, %s)' % (
                    center_id, actual_stats['by_center'][center_id]['ed_open'], open_dt
                )
            )
            for row in csv[3:]:
                center_id = int(row[1])
                # inactive already read from election-day-office-n; make sure it matches
                active_flag = 'No' if 'inactive' in actual_stats['by_center'][center_id] else 'Yes'
                self.assertEqual(row[2], active_flag)

        for center in self.all_centers:
            center_id = center.center_id
            rsp = self._request(reverse('vr_dashboard:election-day-center-n',
                                        args=[center_id]))
            stats = rsp.context['stats']
            actual_center_stats = actual_stats['by_center'][center_id]
            # The last opened time was already read (set to None if it didn't open);
            # make sure it matches the form on this page, which uses 'Not Opened'
            # instead of None for unopened.
            self.assertEqual(
                actual_center_stats['ed_open'] or 'Not Opened',
                stats['last_opened'],
                'Open for center %d different between by-office and by-center pages (%s, %s)' % (
                    center_id, actual_center_stats['ed_open'], stats['last_opened']
                )
            )
            actual_center_stats['last_report'] = stats['last_report']
            for period in ('1', '2', '3', '4'):
                # votes for period is either '' or string form of number
                orig_key = 'reported_period_' + period
                new_key = 'reported_period_' + period + '_count'
                actual_center_stats[new_key] = \
                    self._extract_int_from_span(stats[orig_key]) if stats[orig_key] else 0
            # consistency between what was already extracted for 'inactive' and this response?
            self.assertEqual(
                'inactive' in actual_stats['by_center'][center_id],
                'inactive_for_election' in rsp.context['center']
            )

        # messages from staff phone
        history = self._request(
            reverse('vr_dashboard:phone-history') + '?phone=%s' % self.staff_phone_number
        )
        actual_stats['phone_history'][self.staff_phone_number] = {
            'message_count': len(history.context['sms_messages']),
        }

    def test(self):
        """ This is the one test case in this class; it performs end-to-end
        testing on reporting-api and vr-dashboard, using the following
        steps:

        1. create basic objects like RegistrationCenter (in setUp())
        2. initialize expected and actual stats dictionaries
        3. create different types of data, updating the expected stats
           dictionary to indicate what should appear on the dashboard
        4. run Celery tasks (directly) to regenerate reports based on the
           data created
        5. fetch and log the JSON reports
        6. scrape dashboard screens to get the actual stats reported
        7. compare expected and actual stats
        """
        expected_stats = {
            'by_center': {
                self.rc_1.center_id: {
                    # nothing yet
                },
                self.rc_2.center_id: {
                    # nothing yet
                },
                self.rc_3.center_id: {
                    # nothing yet
                },
                self.rc_4.center_id: {
                    # nothing yet
                },
                self.copy_of_rc_1.center_id: {
                    # nothing yet
                },
                self.rc_5.center_id: {
                    # nothing yet
                }
            },
            'by_office': {
                self.rc_1.office_id: {
                    # nothing yet
                },
                self.rc_2.office_id: {
                    # nothing yet
                },
                self.rc_3.office_id: {
                    # nothing yet
                },
                self.rc_4.office_id: {
                    # nothing yet
                },
                self.copy_of_rc_1.office_id: {
                    # nothing yet
                },
            },
            'summary': deepcopy(EMPTY_SUMMARY),
            'message_stats': {},
            'phone_history': {},
        }
        actual_stats = deepcopy(expected_stats)

        self._describe_infra()
        self._create_election_day_data(expected_stats)
        self._create_registrations(expected_stats)
        self._create_sms_messages(expected_stats)

        # Regenerate reports based on current database contents

        # Make the election day report code think it is now 3:35 p.m. on election day (just
        # after the period 2 time) so that it will flag missing period 1 and 2 reports.
        middle_of_election_day = self.election.polling_start_time.replace(hour=15, minute=35)
        with patch.object(reports, 'get_effective_reminder_time') as mock_reminder_time:
            mock_reminder_time.return_value = middle_of_election_day
            tasks.election_day()
            mock_reminder_time.assert_called()

        tasks.registrations()

        # Log the JSON reports to help with debugging
        credentials = base64.b64encode(self.reporting_user + ':' + self.reporting_password)
        auth_headers = {
            'HTTP_AUTHORIZATION': 'Basic ' + credentials
        }
        for report_rel_url in [test_reports.REGISTRATIONS_REL_URI,
                               test_reports.ELECTION_DAY_LOG_REL_URI,
                               test_reports.ELECTION_DAY_REPORT_REL_URI]:
            url = test_reports.BASE_URI + report_rel_url
            self._request(url, **auth_headers)

        # Scrape the dashboard screens
        self._read_dashboard(actual_stats)

        # Compare expected and actual stats
        logger.info('Expected:')
        logger.info(expected_stats)
        logger.info('Actual:')
        logger.info(actual_stats)
        # Compare some slices of dictionary first to narrow in on the problem
        self.assertDictEqual(expected_stats['summary'], actual_stats['summary'])
        self.assertDictEqual(expected_stats['by_center'], actual_stats['by_center'])
        self.assertDictEqual(expected_stats['by_office'], actual_stats['by_office'])
        # Everything
        self.assertDictEqual(expected_stats, actual_stats)
