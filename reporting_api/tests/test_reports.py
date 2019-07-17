# Python imports
import base64
import json

# 3rd party imports
from django.db import connection
from django.test import TestCase

# Project imports
from register.models import RegistrationCenter
from register.tests.factories import RegistrationFactory
from reporting_api import create_test_data, reports, tasks, views
from reporting_api.data_pull import registrations_by_phone

BASE_URI = '/reporting/'
ELECTION_DAY_REPORT_REL_URI = 'election_day.json'
ELECTION_DAY_LOG_REL_URI = 'election_day_log.json'
REGISTRATIONS_REL_URI = 'registrations.json'

TEST_USERNAME = 'some_test_user'
TEST_PASSWORD = 'some_password'

NUM_REGISTRATIONS = 100
NUM_COPY_CENTERS = 3
NUM_NO_REG_CENTERS = 3


class TestReports(TestCase):
    def setUp(self):
        create_test_data.create(num_registrations=NUM_REGISTRATIONS,
                                num_copy_centers=NUM_COPY_CENTERS,
                                num_no_reg_centers=NUM_NO_REG_CENTERS)
        tasks.election_day()
        tasks.registrations()
        credentials = base64.b64encode((TEST_USERNAME + ':' + TEST_PASSWORD).encode())
        self.client.defaults['HTTP_AUTHORIZATION'] = b'Basic ' + credentials
        views.REPORT_USER_DB[TEST_USERNAME] = TEST_PASSWORD

    def test_log(self):
        rsp = self.client.get(BASE_URI + ELECTION_DAY_LOG_REL_URI)
        self.assertEqual(200, rsp.status_code)
        self.assertEqual('application/json', rsp['Content-Type'])
        self.assertNotEqual('{}', rsp.content.decode())
        allowable_phone_keys = {'phone_number', 'type', 'center_code',
                                'creation_date', 'data'}
        log = json.loads(rsp.content.decode())
        for key in log.keys():
            int(key)  # shouldn't raise
            for phone in log[key]:
                actual_phone_keys = set(phone.keys())
                self.assertTrue(actual_phone_keys.issubset(allowable_phone_keys))
                self.assertEqual(int(key), phone['center_code'])

    def _check_slice(self, d, key_for_slice, required_item_keys=(), forbidden_item_keys=()):
        self.assertIn(key_for_slice, d)
        if isinstance(d[key_for_slice], dict):
            slice_items = [d[key_for_slice][k] for k in d[key_for_slice].keys()]
        else:
            slice_items = d[key_for_slice]
        assert slice_items
        for item in slice_items:
            for k in required_item_keys:
                self.assertIn(k, item)
            for k in forbidden_item_keys:
                self.assertNotIn(k, item)

    def _count_copy_centers(self, by_polling_center):
        copy_centers_found = 0
        if isinstance(by_polling_center, dict):
            by_polling_center = [by_polling_center[key] for key in by_polling_center.keys()]
        for center_dict in by_polling_center:
            if center_dict['polling_center_type'] == RegistrationCenter.Types.COPY:
                copy_centers_found += 1
                self.assertIn('copy_of_polling_center', center_dict)
        return copy_centers_found

    def test_election_day(self):
        rsp = self.client.get(BASE_URI + ELECTION_DAY_REPORT_REL_URI)
        self.assertEqual(200, rsp.status_code)
        self.assertEqual('application/json', rsp['Content-Type'])
        d = json.loads(rsp.content.decode())
        self._check_slice(d, 'by_country',
                          required_item_keys=('country', 'office_count', 'polling_center_count',
                                              'region_count', 'registration_count'),
                          forbidden_item_keys=('copy_of_polling_center', 'polling_center_type',
                                               'inactive_for_election'))
        self._check_slice(d, 'by_office',
                          required_item_keys=('country', 'polling_center_count', 'region',
                                              'registration_count', 'inactive_for_election'),
                          forbidden_item_keys=('copy_of_polling_center', 'polling_center_type'))
        self._check_slice(d, 'by_polling_center',
                          required_item_keys=('country', 'office_id', 'polling_center_code',
                                              'polling_center_type', 'region',
                                              'subconstituency_id', 'registration_count'),
                          forbidden_item_keys=('polling_center_count',))
        self._check_slice(d, 'by_region',
                          required_item_keys=('country', 'office_count', 'polling_center_count',
                                              'region', 'registration_count'),
                          forbidden_item_keys=('copy_of_polling_center', 'polling_center_type',
                                               'inactive_for_election'))
        self.assertEqual(NUM_COPY_CENTERS, self._count_copy_centers(d['by_polling_center']))

    def test_registrations(self):
        rsp = self.client.get(BASE_URI + REGISTRATIONS_REL_URI)
        self.assertEqual(200, rsp.status_code)
        self.assertEqual('application/json', rsp['Content-Type'])
        d = json.loads(rsp.content.decode())
        self._check_slice(d, 'by_country',
                          required_item_keys=('country', 'office_count', 'polling_center_count',
                                              'region_count', 'total'),
                          forbidden_item_keys=('copy_of_polling_center', 'polling_center_type'))
        self._check_slice(d, 'by_office_id',
                          required_item_keys=('country', 'polling_center_count', 'region',
                                              'total'),
                          forbidden_item_keys=('copy_of_polling_center', 'polling_center_type'))
        self._check_slice(d, 'by_polling_center_code',
                          required_item_keys=('country', 'office_id', 'polling_center_code',
                                              'polling_center_type', 'region',
                                              'subconstituency_id'),
                          forbidden_item_keys=('polling_center_count',))
        self._check_slice(d, 'by_region',
                          required_item_keys=('country', 'office_count', 'polling_center_count',
                                              'region', 'total'),
                          forbidden_item_keys=('copy_of_polling_center', 'polling_center_type'))
        self._check_slice(d, 'by_subconstituency_id',
                          required_item_keys=('country', 'office_id', 'polling_center_count',
                                              'region', 'subconstituency_id', 'total'),
                          forbidden_item_keys=('copy_of_polling_center', 'polling_center_type'))
        # Registrations aren't against a copy center, so no copy centers should show up here.
        self.assertEqual(0, self._count_copy_centers(d['by_polling_center_code']))
        # Registrations aren't against a center specifically defined to not support registrations.
        no_reg_centers = RegistrationCenter.objects.filter(reg_open=False)
        reported_centers = [
            center_info['polling_center_code'] for center_info in d['by_polling_center_code']
        ]
        self.assertEqual(NUM_NO_REG_CENTERS, no_reg_centers.count())
        for center in no_reg_centers:
            self.assertNotIn(center.center_id, reported_centers)

    def test_registration_slices(self):
        d = reports.retrieve_report(reports.REGISTRATIONS_METADATA_KEY)
        self.assertEqual(set(d.keys()), {'demographic_breakdowns', 'subconstituencies',
                                         'offices', 'last_updated', 'dates'})
        d = reports.retrieve_report(reports.REGISTRATIONS_STATS_KEY)
        self.assertEqual(set(d.keys()), {'sms_stats', 'phone_multiple_family_book',
                                         'phone_duplicate_registrations', 'message_stats',
                                         'headline'})

    def test_lists_of_reports(self):
        r1, r2 = reports.retrieve_report([reports.REGISTRATIONS_METADATA_KEY,
                                          reports.REGISTRATIONS_STATS_KEY])
        self.assertTrue(bool(r1))
        self.assertTrue(bool(r2))

        class BadElection(object):

            def __init__(self):
                self.id = -1234

        election_with_bogus_id = BadElection()
        r1, r2 = reports.retrieve_report([
            reports.REGISTRATIONS_METADATA_KEY,
            reports.election_key(reports.ELECTION_DAY_METADATA_KEY, election_with_bogus_id)
        ])
        # although _METADATA_ exists, 1st result is None to indicate that something failed
        self.assertFalse(bool(r1))
        # 2nd result is None because there's no such election
        self.assertFalse(bool(r2))


class TestRegistrationsByPhone(TestCase):

    @classmethod
    def setUpTestData(cls):
        # create a registration and record the phone number
        cls.reg = RegistrationFactory(archive_time=None)
        cls.phone_number = cls.reg.sms.from_number
        cls.cursor = connection.cursor()

    def test_registrations_by_phone_report_is_correct(self):
        # create a second registration with the same phone number
        RegistrationFactory(sms__from_number=self.phone_number, archive_time=None)
        report = registrations_by_phone(self.cursor)
        self.assertEqual(report, [(self.phone_number, 2)])

    def test_multiple_rows(self):
        # create a second registration with the same phone number
        RegistrationFactory(sms__from_number=self.phone_number, archive_time=None)
        # create 3 more registrations sharing a phone number (but different than the previous two)
        reg_group_2 = RegistrationFactory(archive_time=None)
        second_phone_number = reg_group_2.sms.from_number
        RegistrationFactory(sms__from_number=second_phone_number, archive_time=None)
        RegistrationFactory(sms__from_number=second_phone_number, archive_time=None)
        report = registrations_by_phone(self.cursor)
        expected_report = [
            (self.phone_number, 2),
            (second_phone_number, 3),
        ]
        self.assertEqual(sorted(report), sorted(expected_report))

    def test_ignore_singletons(self):
        "Phone numbers with only 1 registration are not included in the report."
        report = registrations_by_phone(self.cursor)
        self.assertEqual(report, [])

    def test_ignore_deleted_sms(self):
        RegistrationFactory(sms__from_number=self.phone_number, sms__deleted=True,
                            archive_time=None)
        report = registrations_by_phone(self.cursor)
        self.assertEqual(report, [])

    def test_ignore_deleted_registration(self):
        RegistrationFactory(sms__from_number=self.phone_number, deleted=True,
                            archive_time=None)
        report = registrations_by_phone(self.cursor)
        self.assertEqual(report, [])

    def test_ignore_archived_registration(self):
        RegistrationFactory(sms__from_number=self.phone_number)
        report = registrations_by_phone(self.cursor)
        self.assertEqual(report, [])


class TestMissingReports(TestCase):

    def setUp(self):
        # The client in this test class can log in okay but reports aren't
        # present.
        reports.empty_report_store()
        credentials = base64.b64encode((TEST_USERNAME + ':' + TEST_PASSWORD).encode())
        self.client.defaults['HTTP_AUTHORIZATION'] = b'Basic ' + credentials
        views.REPORT_USER_DB[TEST_USERNAME] = TEST_PASSWORD

    def test(self):
        for relative_uri in (REGISTRATIONS_REL_URI, ELECTION_DAY_LOG_REL_URI,
                             ELECTION_DAY_REPORT_REL_URI):
            rsp = self.client.get(BASE_URI + relative_uri)
            self.assertEqual(503, rsp.status_code, 'expected report at %s to be unavailable' %
                             relative_uri)
            self.assertEqual('text/plain', rsp['Content-Type'])


class TestNoAuth(TestCase):
    def setUp(self):
        views.REPORT_USER_DB.clear()

    def test_election_day_log(self):
        rsp = self.client.get(BASE_URI + ELECTION_DAY_LOG_REL_URI)
        self.assertEqual(401, rsp.status_code)


class TestBadAuth(TestCase):
    def setUp(self):
        views.REPORT_USER_DB.clear()
        views.REPORT_USER_DB['validuser'] = 'validpass'
        credentials = base64.b64encode('invaliduser:invalidpass'.encode())
        self.client.defaults['HTTP_AUTHORIZATION'] = b'Basic ' + credentials

    def test_election_day_log(self):
        rsp = self.client.get(BASE_URI + ELECTION_DAY_LOG_REL_URI)
        self.assertEqual(401, rsp.status_code)


class TestNoAuthDB(TestCase):
    """ REPORT_USER_DB is empty, and we try to log in.  It fails of
    course, and if you look in the log you should see a hint that
    the user database is not set up.
    """

    def setUp(self):
        views.REPORT_USER_DB.clear()
        credentials = base64.b64encode('anyuser:anypass'.encode())
        self.client.defaults['HTTP_AUTHORIZATION'] = b'Basic ' + credentials

    def test_election_day_log(self):
        rsp = self.client.get(BASE_URI + ELECTION_DAY_LOG_REL_URI)
        self.assertEqual(401, rsp.status_code)
