from datetime import timedelta

# 3rd party imports
from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils.timezone import now

from libya_site.tests.factories import DEFAULT_USER_PASSWORD, UserFactory
from register.models import Registration
from register.tests.factories import OfficeFactory, RegistrationCenterFactory
from reporting_api import create_test_data, tasks
from reporting_api.reports import empty_report_store
from voting.models import Election
from voting.tests.factories import ElectionFactory
from vr_dashboard.views.views import ELECTION_SESSION_KEY

URI_NAMESPACE = 'vr_dashboard:'

# all URIs which contain no parameters
ALL_URI_NAMES = ('csv', 'daily-csv', 'election-day', 'election-day-center', 'national', 'offices',
                 'offices-detail', 'regions', 'sms', 'subconstituencies', 'weekly',
                 'reports', 'center-csv',
                 'election-day-hq', 'election-day-preliminary')
PUBLIC_URI_NAMES = ('national', 'offices', 'regions')
# simple URIs that also support a CSV rendering
SUPPORT_CSV_FORMAT = ('election-day', 'election-day-center')

NUM_REGISTRATIONS = 100


class TestElectionSelection(TestCase):

    def setUp(self):
        self.election_1 = ElectionFactory(
            polling_start_time=now() - timedelta(days=10),
            polling_end_time=now() - timedelta(days=9)
        )
        self.election_2 = ElectionFactory(
            polling_start_time=now() - timedelta(days=4),
            polling_end_time=now() - timedelta(days=3)
        )
        self.staff_user = UserFactory()
        self.staff_user.is_staff = True
        self.staff_user.save()

    def test_election_in_session(self):
        assert self.client.login(username=self.staff_user.username, password=DEFAULT_USER_PASSWORD)
        self.client.get(reverse('vr_dashboard:election-day'))
        self.assertEqual(self.client.session[ELECTION_SESSION_KEY],
                         Election.objects.get_most_current_election().id)
        self.client.get(reverse('vr_dashboard:election-day') + '?election=%d' % self.election_1.id)
        self.assertEqual(self.client.session[ELECTION_SESSION_KEY], self.election_1.id)
        self.client.get(reverse('vr_dashboard:election-day-center'))
        self.assertEqual(self.client.session[ELECTION_SESSION_KEY], self.election_1.id)
        self.client.get(reverse('vr_dashboard:election-day-center')
                        + '?election=%d' % self.election_2.id)
        self.assertEqual(self.client.session[ELECTION_SESSION_KEY], self.election_2.id)
        self.client.get(reverse('vr_dashboard:election-day'))
        self.assertEqual(self.client.session[ELECTION_SESSION_KEY], self.election_2.id)


class TestRegistrationData(TestCase):

    def setUp(self):
        create_test_data.create(num_registrations=NUM_REGISTRATIONS)
        self.unused_center = RegistrationCenterFactory()
        self.unused_office = OfficeFactory()
        tasks.election_day()
        tasks.registrations()
        self.staff_user = UserFactory()
        self.staff_user.is_staff = True
        self.staff_user.save()

    @override_settings(HIDE_PUBLIC_DASHBOARD=True)
    def test_auth_hiding_public(self):
        """
        When user not logged in,
        ensure that we get a redirect to the login page for non-public pages.
        and to the HNEC site for public pages.
         """
        for uri_name in ALL_URI_NAMES:
            uri = reverse(URI_NAMESPACE + uri_name)
            rsp = self.client.get(uri)
            if uri_name in PUBLIC_URI_NAMES:
                self.assertRedirects(rsp, settings.PUBLIC_REDIRECT_URL,
                                     fetch_redirect_response=False,
                                     msg_prefix='Path %s not handled properly' % uri)
            else:
                self.assertRedirects(rsp, reverse(settings.LOGIN_URL) + "?next=" + uri,
                                     msg_prefix='Path %s not handled properly' % uri)

    @override_settings(HIDE_PUBLIC_DASHBOARD=False)
    def test_auth_not_hiding_public(self):
        """
        When user not logged in,
        ensure that we get a redirect to the login page for non-public pages,
        but not for public pages.
        """
        for uri_name in ALL_URI_NAMES:
            uri = reverse(URI_NAMESPACE + uri_name)
            rsp = self.client.get(uri)
            if uri_name in PUBLIC_URI_NAMES:
                self.assertEqual(200, rsp.status_code,
                                 'Request to %s failed with status %d' % (uri, rsp.status_code))
            else:
                self.assertRedirects(rsp, reverse(settings.LOGIN_URL) + "?next=" + uri,
                                     msg_prefix='Path %s not handled properly' % uri)

    @override_settings(HIDE_PUBLIC_DASHBOARD=True)
    def test_staff_not_hiding_public(self):
        """
        When a staff user is logged in, they can view "public" pages
        even if HIDE_PUBLIC_DASHBOARD is True.
        """
        assert self.client.login(username=self.staff_user.username, password=DEFAULT_USER_PASSWORD)
        for uri_name in PUBLIC_URI_NAMES:
            uri = reverse(URI_NAMESPACE + uri_name)
            rsp = self.client.get(uri)
            self.assertEqual(200, rsp.status_code,
                             'Request to %s failed with status %d' % (uri, rsp.status_code))

    def test_basic_operation(self):
        """  For the time being, simply ensure that the VR dashboard pages don't blow up. """
        assert self.client.login(username=self.staff_user.username, password=DEFAULT_USER_PASSWORD)
        for uri_name in ALL_URI_NAMES:
            uri = reverse(URI_NAMESPACE + uri_name)
            rsp = self.client.get(uri)
            self.assertEqual(200, rsp.status_code,
                             'Request to %s failed with status %d' % (uri, rsp.status_code))
            if uri_name in SUPPORT_CSV_FORMAT:
                rsp = self.client.get(uri + '?format=csv')
                self.assertEqual(200, rsp.status_code,
                                 'CSV request to %s failed with status %d' % (uri, rsp.status_code))
        # pages without fixed paths
        # test election-day-office-n with both default and CSV renderings
        # First, we must find an office that actually has registrations
        some_valid_office_id = Registration.objects.first().registration_center.office.id
        uri = reverse(URI_NAMESPACE + 'election-day-office-n', args=[some_valid_office_id])
        rsp = self.client.get(uri)
        self.assertEqual(200, rsp.status_code,
                         'Request to %s failed with status %d' % (uri, rsp.status_code))
        rsp = self.client.get(uri + '?format=csv')
        self.assertEqual(200, rsp.status_code,
                         'Request to %s failed with status %d' % (uri, rsp.status_code))

    def test_invalid_office_center(self):
        assert self.client.login(username=self.staff_user.username, password=DEFAULT_USER_PASSWORD)
        # We should get 404 from truly bogus ids as well as from centers or offices that
        # exist but aren't used.
        for input_uri_name, invalid_id in [
            ('vr_dashboard:election-day-center-n', self.unused_center.id),
            ('vr_dashboard:election-day-center-n', 999999),
            ('vr_dashboard:election-day-office-n', self.unused_office.id),
            ('vr_dashboard:election-day-office-n', 999999)
        ]:
            uri = reverse(input_uri_name, args=[invalid_id])
            rsp = self.client.get(uri)
            self.assertContains(rsp, str(invalid_id), status_code=404)


class TestWithNoRegistrationData(TestCase):

    def setUp(self):
        create_test_data.create(num_registrations=0, num_registration_dates=0)
        tasks.election_day()
        tasks.registrations()
        self.staff_user = UserFactory()
        self.staff_user.is_staff = True
        self.staff_user.save()

    def test_basic_operation(self):
        """  For the time being, simply ensure that the VR dashboard pages (and report generation tasks)
        don't blow up when there aren't any registrations. """
        assert self.client.login(username=self.staff_user.username, password=DEFAULT_USER_PASSWORD)
        for uri_name in ALL_URI_NAMES:
            uri = reverse(URI_NAMESPACE + uri_name)
            rsp = self.client.get(uri)
            self.assertEqual(200, rsp.status_code,
                             'Request to %s failed with status %d' % (uri, rsp.status_code))


class TestWithNoGeneratedReports(TestCase):

    @classmethod
    def setUpTestData(cls):  # No database changes
        empty_report_store()

    def setUp(self):
        self.staff_user = UserFactory()
        self.staff_user.is_staff = True
        self.staff_user.save()

    def test_no_report_error(self):
        expected_page_flags = {
            'election-day': ['election_day_overview_page', 'staff_page'],
            'election-day-center': ['election_day_center_page', 'staff_page'],
            'election-day-hq': ['election_day_hq_page', 'staff_page'],
            'election-day-preliminary': ['election_day_preliminary_votes_page', 'staff_page']
        }
        expected_status_code = 503
        assert self.client.login(username=self.staff_user.username, password=DEFAULT_USER_PASSWORD)
        for uri_name in ALL_URI_NAMES:
            uri = reverse(URI_NAMESPACE + uri_name)
            rsp = self.client.get(uri)
            self.assertEqual(expected_status_code, rsp.status_code,
                             'Request to %s had status %d instead of %d'
                             % (uri, rsp.status_code, expected_status_code))
            if uri_name in expected_page_flags:
                for expected in expected_page_flags[uri_name]:
                    self.assertIn(
                        expected, rsp.context,
                        'Error page for %s doesn\'t set page flag "%s"' % (uri_name, expected)
                    )
        for uri_name in ['election-day-office-n', 'election-day-center-n']:
            uri = reverse(URI_NAMESPACE + uri_name, args=[999999])
            rsp = self.client.get(uri)
            self.assertEqual(expected_status_code, rsp.status_code,
                             'Request to %s had status %d instead of %d'
                             % (uri, rsp.status_code, expected_status_code))


class TestRedirects(TestCase):

    @override_settings(HIDE_PUBLIC_DASHBOARD=False)
    def test_dashboard_root_redirects(self):
        """ /data goes to /data/ because it needs a trailing slash (via
        Django), and /data/ goes to /data/national/ because that's the
        default dashboard dashboard page (via a view).
        """
        rsp = self.client.get('/data')
        self.assertRedirects(rsp, '/data/', status_code=301,
                             fetch_redirect_response=False)
        rsp = self.client.get('/data/')
        self.assertRedirects(rsp, reverse(URI_NAMESPACE + 'national'),
                             fetch_redirect_response=False)
