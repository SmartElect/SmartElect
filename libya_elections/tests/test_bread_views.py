from django.core.urlresolvers import NoReverseMatch, reverse
from django.test import TestCase, RequestFactory

from libya_elections.tests.utils import ResponseCheckerMixin
from libya_site.tests.factories import UserFactory
from register.models import SMS
from register.tests.factories import SMSFactory
from staff.tests.base import StaffUserMixin

# Get the Bread
from bulk_sms.views import BroadcastBread
from civil_registry.views import CitizenBread
from polling_reports.views import CenterClosedForElectionBread, CenterOpenBread, PollingReportBread, \
    PreliminaryVoteCountBread
from register.views import BlacklistedNumberBread, ConstituencyBread, OfficeBread, RegistrationBread, \
    RegistrationCenterBread, SMSBread, StaffPhoneBread, SubconstituencyBread, WhitelistedNumberBread
from rollgen.views import StationBread
from staff.views import UserBread
from voting.views import BallotBread, CandidateBread, ElectionBread

models = (
    BallotBread,
    BlacklistedNumberBread,
    BroadcastBread,
    CandidateBread,
    CenterClosedForElectionBread,
    CenterOpenBread,
    CitizenBread,
    ConstituencyBread,
    ElectionBread,
    OfficeBread,
    PollingReportBread,
    PreliminaryVoteCountBread,
    RegistrationBread,
    RegistrationCenterBread,
    SMSBread,
    StaffPhoneBread,
    StationBread,
    SubconstituencyBread,
    UserBread,
    WhitelistedNumberBread,
)


class TestBreadViews(ResponseCheckerMixin, TestCase):
    """Double check that generic and anonymous site users can't access bread views."""

    def test_access(self):
        UserFactory(username='joe', password='puppy')
        for m in models:
            instance = m()
            urls = instance.get_urls()
            for url in urls:
                try:
                    path = reverse(url.name)
                except NoReverseMatch:
                    path = reverse(url.name, args=[1])
                self.client.login(username='joe', password='puppy')
                self.assertForbidden(self.client.get(path))
                self.client.logout()
                self.assertRedirectsToLogin(self.client.get(path))


class PaginationContext(StaffUserMixin, TestCase):
    """Ensure proper pagination structures are placed in the template context"""
    permissions = ['browse_sms', ]
    model = SMS

    def setUp(self):
        super(PaginationContext, self).setUp()
        self.factory = RequestFactory()
        self.url = reverse('browse_messages')
        self.request = self.create_request(self.url)
        sms_bread = SMSBread()
        # paginate by 1, to make it easier to test pages
        sms_bread.browse_view.paginate_by = 1
        self.browse_view = sms_bread.get_browse_view()

    def create_request(self, url=None, page=None):
        if not url:
            url = self.url
        if page:
            url = '{}?page={}'.format(url, page)
        request = self.factory.get(url)
        request.user = self.user
        return request

    def test_dont_throw_error_if_pagination_is_off(self):
        unpaginated_sms_bread = SMSBread()
        unpaginated_sms_bread.browse_view.paginate_by = None
        browse_view = unpaginated_sms_bread.get_browse_view()
        context = browse_view(self.request).context_data
        self.assertFalse(context['paginator'])
        self.assertEqual(context['is_paginated'], False)

    def test_only_one_page(self):
        context = self.browse_view(self.request).context_data
        self.assertTrue(context['paginator'])
        self.assertEqual(context['is_paginated'], False)

    def test_head_pages_have_links(self):
        SMSFactory.create_batch(size=2)
        paginator_links = self.browse_view(self.request).context_data['paginator_links']
        page_2_url = self.url + '?page=2'
        self.assertEqual(paginator_links, [[None, 1], [page_2_url, 2]])

    def test_tail_pages_have_links(self):
        SMSFactory.create_batch(size=8)
        paginator_links = self.browse_view(self.request).context_data['paginator_links']
        page_8_url = self.url + '?page=8'
        self.assertIn([page_8_url, 8], paginator_links)

    def test_surrounding_pages_have_links(self):
        SMSFactory.create_batch(size=8)
        request = self.create_request(page=5)
        paginator_links = self.browse_view(request).context_data['paginator_links']
        page_4_url = self.url + '?page=4'
        page_6_url = self.url + '?page=6'
        self.assertIn([page_4_url, 4], paginator_links)
        self.assertIn([page_6_url, 6], paginator_links)
        # page 3 is not in the list (it's elided)
        page_3_url = self.url + '?page=3'
        self.assertNotIn([page_3_url, 3], paginator_links)

    def test_complex_example(self):
        # Request page 3 of an 8 page listing. Make sure that page 2 isn't included twice (for being
        # in head and being a surrounding page), and also test that the proper pages are elided
        # after the surrounding pages.
        SMSFactory.create_batch(size=8)
        request = self.create_request(page=3)
        paginator_links = self.browse_view(request).context_data['paginator_links']
        page_1_url = self.url + '?page=1'
        page_2_url = self.url + '?page=2'
        page_4_url = self.url + '?page=4'
        page_7_url = self.url + '?page=7'
        page_8_url = self.url + '?page=8'
        expected_links = [
            [page_1_url, 1],
            [page_2_url, 2],
            [None, 3],
            [page_4_url, 4],
            [None, None],  # ellipsis
            # page 6 is covered by the ellipsis
            [page_7_url, 7],
            [page_8_url, 8],
        ]
        self.assertEqual(paginator_links, expected_links)
