import datetime

from django.conf import settings
from django.test import TestCase
from django.utils.timezone import now
from pytz import timezone

from libya_elections.utils import astz
from polling_reports.models import CenterOpen
from polling_reports.tests.factories import StaffPhoneFactory
from register.models import Office
from register.tests.factories import RegistrationCenterFactory
from voting.models import Election
from voting.tests.factories import ElectionFactory

from reporting_api import create_test_data, tasks
from reporting_api.data_pull_common import get_all_polling_locations
from reporting_api.data_pull_ed import message_log, pull_data, process_raw_data
from reporting_api.reports import ELECTION_DAY_HQ_REPORTS_KEY, ELECTION_DAY_REPORT_KEY, \
    ELECTION_DAY_LOG_KEY, election_key, retrieve_report, get_election_data_from_db


class ElectionDayTest(TestCase):

    def setUp(self):
        self.original = RegistrationCenterFactory()
        self.copy = RegistrationCenterFactory(copy_of=self.original)
        self.polling_locations = get_all_polling_locations()
        self.election = ElectionFactory(
            polling_start_time=now() - datetime.timedelta(hours=1),
            polling_end_time=now() + datetime.timedelta(hours=1),
        )
        # add decoy elections before/after the real one
        self.decoy_before_election = ElectionFactory(
            polling_start_time=self.election.polling_start_time - datetime.timedelta(days=5),
            polling_end_time=self.election.polling_end_time - datetime.timedelta(days=5),
        )
        self.decoy_after_election = ElectionFactory(
            polling_start_time=self.election.polling_start_time + datetime.timedelta(days=5),
            polling_end_time=self.election.polling_end_time + datetime.timedelta(days=5),
        )
        self.test_office_1 = 1
        self.test_office_2 = 2
        self.test_region = 3
        self.polling_centers = {
            '11001': {
                'polling_center_code': 11001,
                'office_id': self.test_office_1,
                'subconstituency_id': 2,
                'region': Office.REGION_NAMES[self.test_region],
                'country': 'Libya'
            },
            '11002': {
                'polling_center_code': 11002,
                'office_id': self.test_office_2,
                'subconstituency_id': 2,
                'region': Office.REGION_NAMES[self.test_region],
                'country': 'Libya'
            },
            '11003': {
                'polling_center_code': 11003,
                'office_id': self.test_office_1,
                'subconstituency_id': 2,
                'region': Office.REGION_NAMES[self.test_region],
                'country': 'Libya'
            }
        }
        self.center_opens = []
        self.center_reports = []
        self.inactive_for_election = ['11003']

    def test_copy_repr(self):
        self.assertEqual(self.polling_locations[self.original.center_id][3],
                         None)
        self.assertEqual(self.polling_locations[self.copy.center_id][3],
                         self.original.center_id)

    def test_last_updated(self):
        result = pull_data(self.polling_locations, self.election)
        last_updated = datetime.datetime.strptime(result['last_updated'], '%Y-%m-%dT%X.%f')
        # last updated is what we expect (within a minute)
        self.assertTrue((last_updated - datetime.datetime.now()) < datetime.timedelta(minutes=1))

    def test_output_schema(self):
        result = pull_data(self.polling_locations, self.election)
        self.assertIn('dates', result)
        self.assertIn('by_polling_center', result)
        self.assertIn('by_country', result)
        self.assertIn('by_office', result)
        self.assertIn('offices', result)
        self.assertIn('by_region', result)

    def test_opened(self):
        feb20 = datetime.date(2014, 2, 20)
        self.center_opens = [
            {'polling_center_code': '11001', 'date': feb20, 'opened': datetime.time(8, 13, 21)},
        ]
        center_vote_counts = dict()
        result = process_raw_data(self.polling_centers, self.inactive_for_election,
                                  self.center_opens, self.center_reports, center_vote_counts)
        self.assertEqual(result['dates'], ['2014-02-20'])
        self.assertIn('11001', result['by_polling_center'])
        self.assertEqual(result['by_polling_center']['11001']['2014-02-20']['opened'], '08:13:21')

    def test_duplicate_reports(self):
        # The processing code does not reorder data. It relies on the ordering set in
        # the database query. This test just verifies that the last report per period is
        # the one that counts (irrespective of the timestamp)
        feb20 = datetime.date(2014, 2, 20)
        self.center_reports = [
            {'polling_center_code': '11001',
             'date': feb20,
             'reported': datetime.time(1, 0, 0),
             'voting_period': '1',
             'votes_reported': 8},
            {'polling_center_code': '11001',
             'date': feb20,
             'reported': datetime.time(2, 0, 0),
             'voting_period': '1',
             'votes_reported': 58},
        ]
        center_vote_counts = dict()
        result = process_raw_data(self.polling_centers, self.inactive_for_election,
                                  self.center_opens, self.center_reports, center_vote_counts)
        votes = result['by_polling_center']['11001']['2014-02-20']['1']
        self.assertEqual(votes, 58)

        # even if we make the first report 'later', it doesn't matter
        self.center_reports[0]['reported'] = datetime.time(3, 0, 0)
        result = process_raw_data(self.polling_centers, self.inactive_for_election,
                                  self.center_opens, self.center_reports, center_vote_counts)
        votes = result['by_polling_center']['11001']['2014-02-20']['1']
        self.assertEqual(votes, 58)
        # therefore, the key is to get your ordering right in the database query

    def test_inactive(self):
        result = process_raw_data(self.polling_centers, self.inactive_for_election,
                                  self.center_opens, self.center_reports, dict())
        self.assertEqual(result['by_office'][self.test_office_1]['inactive_for_election'], [11003])
        self.assertEqual(result['by_office'][self.test_office_2]['inactive_for_election'], [])
        self.assertEqual(result['by_polling_center']['11003']['inactive_for_election'], True)

    def test_prelim_vote_count_rollup(self):
        center_reports = [
            {'polling_center_code': '11001',
             'date': now(),
             'reported': datetime.time(1, 0, 0),
             'voting_period': '1',
             'votes_reported': 8},
        ]
        center_vote_counts = {
            '11001': {
                'country': 'Libya',
                'office_id': self.test_office_1,
                'polling_center_code': 11001,
                'prelim_counts': {
                    1: 25,
                    2: 50
                },
                'region': self.test_region
            },
            '11002': {
                'country': 'Libya',
                'office_id': self.test_office_2,
                'polling_center_code': 11002,
                'prelim_counts': {
                    1: 14
                },
                'region': self.test_region
            }
        }
        result = process_raw_data(self.polling_centers, self.inactive_for_election,
                                  self.center_opens, center_reports, center_vote_counts)

        prelim_counts = result['by_country']['Libya']['prelim_counts']
        self.assertEqual(prelim_counts[1], 39)
        self.assertEqual(prelim_counts[2], 50)

        prelim_counts = result['by_region'][Office.REGION_NAMES[self.test_region]]['prelim_counts']
        self.assertEqual(prelim_counts[1], 39)
        self.assertEqual(prelim_counts[2], 50)

        prelim_counts = result['by_office'][self.test_office_1]['prelim_counts']
        self.assertEqual(prelim_counts[1], 25)
        self.assertEqual(prelim_counts[2], 50)

        prelim_counts = result['by_office'][self.test_office_2]['prelim_counts']
        self.assertEqual(prelim_counts[1], 14)
        self.assertFalse(2 in prelim_counts)


class TestStaffPhoneReportingByElection(TestCase):
    """ StaffPhone objects aren't tied explicitly to an election, but
    a StaffPhone object created after the end of an election shouldn't
    be reported for that election.

    Create two StaffPhone objects per election, one at the very start
    and one at the very end.  Verify that, for each election, the reported
    messages are all StaffPhone objects up until the very end of that
    election.
    """

    def test(self):
        center = RegistrationCenterFactory()
        elections = [
            {'polling_start_time': now() - datetime.timedelta(days=60)},
            {'polling_start_time': now() - datetime.timedelta(days=40)},
            {'polling_start_time': now() - datetime.timedelta(days=20)},
        ]

        for election in elections:
            election['polling_end_time'] = \
                election['polling_start_time'] + datetime.timedelta(hours=6)
            election['object'] = ElectionFactory(
                polling_start_time=election['polling_start_time'],
                polling_end_time=election['polling_end_time'],
            )
            election['staff_phone_1'] = StaffPhoneFactory(
                registration_center=center,
                creation_date=election['object'].work_start_time
            )
            election['staff_phone_2'] = StaffPhoneFactory(
                registration_center=center,
                creation_date=election['object'].work_end_time
            )

        for i, election in enumerate(elections, start=1):
            messages_for_center = message_log(election['object'])[center.center_id]
            self.assertEqual(len(messages_for_center), i * 2)
            # check for other junk leaking into the testcase
            for message in messages_for_center:
                self.assertEqual(message['type'], 'phonelink')


class TestReportingByElection(TestCase):

    def setUp(self):
        self.election_dates = (
            now() - datetime.timedelta(days=20),
            now() - datetime.timedelta(days=10),
            now()
        )
        create_test_data.create(num_registrations=10,
                                num_copy_centers=0,
                                election_dates=self.election_dates)
        tasks.election_day()
        # do it again, to ensure we don't try to add duplicate records to ElectionReport table
        tasks.election_day()

    def test_db_versus_redis(self):
        for election in Election.objects.all():
            report_from_db, hq_reports_from_db, messages_from_db = \
                get_election_data_from_db(election)
            self.assertIsNotNone(report_from_db)
            self.assertIsNotNone(hq_reports_from_db)
            self.assertIsNotNone(messages_from_db)
            report_from_redis = retrieve_report(election_key(ELECTION_DAY_REPORT_KEY, election))
            hq_reports_from_redis = \
                retrieve_report(election_key(ELECTION_DAY_HQ_REPORTS_KEY, election))
            messages_from_redis = retrieve_report(election_key(ELECTION_DAY_LOG_KEY, election))
            self.assertIsNotNone(report_from_redis)
            self.assertIsNotNone(hq_reports_from_redis)
            self.assertIsNotNone(messages_from_redis)
            self.assertDictEqual(report_from_db, report_from_redis)
            self.assertDictEqual(hq_reports_from_db, hq_reports_from_redis)
            self.assertDictEqual(messages_from_db, messages_from_redis)

    def test_distribution_by_election(self):
        tz = timezone(settings.TIME_ZONE)
        elections = Election.objects.all()

        # for each election, grab the report and initialize a counter for CenterOpen objects
        for election in elections:
            election.report = retrieve_report(election_key(ELECTION_DAY_REPORT_KEY, election))
            election.center_opens_found = 0

        # for each CenterOpen in the db, bump the counter for the particular election
        for center_open in CenterOpen.objects.all():
            open_date_str = astz(center_open.creation_date, tz).strftime('%Y-%m-%d')
            for election in elections:
                if open_date_str in election.report['dates']:
                    election.center_opens_found += 1

        for election in elections:
            center_opens_expected = 0
            for d in election.report['dates']:
                for office_data in election.report['by_office'].values():
                    if d in office_data and 'opened' in office_data[d]:
                        center_opens_expected += office_data[d]['opened']
            self.assertEqual(center_opens_expected, election.center_opens_found)
