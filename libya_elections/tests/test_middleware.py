from datetime import timedelta

from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils.timezone import now

from help_desk.models import ActiveRange
from help_desk.utils import create_help_desk_groups
from help_desk.tests.factories import HelpDeskUserFactory


@override_settings(LANGUAGE_CODE='en')
class NormalizeLanguageCodeMiddlewareTestCase(TestCase):
    def setUp(self):
        self.url = reverse(settings.LOGIN_URL)

    def test_simple_positive_case(self):
        """test that a request with no accept-language header gets the default language"""
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, '<html lang="en"', status_code=200)

    def test_accept_language_overrides_settings(self):
        """test that a simple accept-language header is respected"""
        response = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE='ar')
        self.assertEqual(200, response.status_code)
        self.assertContains(response, '<html lang="ar"', status_code=200)

    def test_yandex_accept_language(self):
        """test the actual accept-language header (from the yandex bot) reported in issue 1351"""
        http_accept_language = 'ru, uk;q=0.8, be;q=0.8, en;q=0.7, *;q=0.01'
        response = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE=http_accept_language)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, '<html lang="en"', status_code=200)

    def test_accept_language_with_subcode_overrides_settings(self):
        """test that an accept-language header with a subcode is respected and normalized"""
        response = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE='ar-ly')
        self.assertEqual(200, response.status_code)
        self.assertContains(response, '<html lang="ar"', status_code=200)

    def test_accept_language_with_subcode_not_case_sensitive(self):
        """test that the middleware that examines the accept-language header ignores case"""
        response = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE='en-US')
        self.assertEqual(200, response.status_code)
        self.assertContains(response, '<html lang="en"', status_code=200)

    def test_unknown_language_reverts_to_settings(self):
        """test that an accept-language header with an unknown language reverts to the default"""
        response = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE='sv')
        self.assertEqual(200, response.status_code)
        self.assertContains(response, '<html lang="en"', status_code=200)


class GroupExpirationMiddlewareTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        create_help_desk_groups()
        cls.password = 'fakepassword'
        cls.user = HelpDeskUserFactory(password=cls.password)
        cls.active_range = ActiveRange.objects.create(user=cls.user)

    def setUp(self):
        self.client.login(username=self.user.username, password=self.password)
        self.url = reverse('check_registration')

    def check_message(self, rsp, expected_message):
        """
        Helper method to check that a response has a 200 status code, and that it
        has a single django contrib message matching `expected_message`. If
        `expected_message` is None, then make sure that there are no messages
        being shown to the user.
        """
        self.assertEqual(rsp.status_code, 200)
        message_list = list(rsp.context['messages'])
        if expected_message:
            self.assertEqual(len(message_list), 1)
            self.assertEqual(expected_message, str(message_list[0]))
        else:
            self.assertEqual(len(message_list), 0)

    def test_after_active_range(self):
        yesterday = now().date() - timedelta(days=1)
        self.active_range.end_date = yesterday
        self.active_range.save()
        rsp = self.client.get(self.url, follow=True)
        # user is shown an error message ...
        self.check_message(rsp, 'This account no longer has staff access.')
        self.user.refresh_from_db()
        # ... and user is no longer a member of any groups
        self.assertFalse(self.user.groups.exists())

    def test_in_active_range(self):
        tomorrow = now().date() + timedelta(days=1)
        self.active_range.end_date = tomorrow
        self.active_range.save()
        rsp = self.client.get(self.url, follow=True)
        # No error message ...
        self.check_message(rsp, None)
        self.user.refresh_from_db()
        # ... and user is still in groups
        self.assertTrue(self.user.groups.exists())

    def test_at_range_end(self):
        self.active_range.end_date = now().date()
        self.active_range.save()
        rsp = self.client.get(self.url, follow=True)
        # No error message ...
        self.check_message(rsp, None)
        self.user.refresh_from_db()
        # ... and user is still in groups
        self.assertTrue(self.user.groups.exists())

    def test_anonymous_user_not_affected(self):
        self.client.logout()
        rsp = self.client.get(self.url, follow=True)
        # No error message.
        self.check_message(rsp, None)

    def test_user_without_active_range_not_affected(self):
        ActiveRange.objects.unfiltered().delete()
        rsp = self.client.get(self.url)
        self.assertEqual(rsp.status_code, 200)
        # No error message ...
        self.check_message(rsp, None)
        self.user.refresh_from_db()
        # ... and user is still in groups
        self.assertTrue(self.user.groups.exists())
