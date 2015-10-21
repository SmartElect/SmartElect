from __future__ import division
from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.utils import override_settings


@override_settings(LANGUAGE_CODE='en')
class NormalizeLanguageCodeMiddlewareTestCase(TestCase):
    def setUp(self):
        self.url = reverse('auth_login')

    def test_simple_positive_case(self):
        """test that a request with no accept-language header gets the default language"""
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, '<html lang="en"', status_code=200)

    def test_accept_language_overrides_settings(self):
        """test that a simple accept-language header is respected"""
        url = reverse('auth_login')
        response = self.client.get(url, HTTP_ACCEPT_LANGUAGE='ar')
        self.assertEqual(200, response.status_code)
        self.assertContains(response, '<html lang="ar"', status_code=200)

    def test_yandex_accept_language(self):
        """test the actual accept-language header (from the yandex bot) reported in issue 1351"""
        url = reverse('auth_login')
        http_accept_language = 'ru, uk;q=0.8, be;q=0.8, en;q=0.7, *;q=0.01'
        response = self.client.get(url, HTTP_ACCEPT_LANGUAGE=http_accept_language)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, '<html lang="en"', status_code=200)

    def test_accept_language_with_subcode_overrides_settings(self):
        """test that an accept-language header with a subcode is respected and normalized"""
        url = reverse('auth_login')
        response = self.client.get(url, HTTP_ACCEPT_LANGUAGE='ar-ly')
        self.assertEqual(200, response.status_code)
        self.assertContains(response, '<html lang="ar"', status_code=200)

    def test_accept_language_with_subcode_not_case_sensitive(self):
        """test that the middleware that examines the accept-language header ignores case"""
        url = reverse('auth_login')
        response = self.client.get(url, HTTP_ACCEPT_LANGUAGE='en-US')
        self.assertEqual(200, response.status_code)
        self.assertContains(response, '<html lang="en"', status_code=200)

    def test_unknown_language_reverts_to_settings(self):
        """test that an accept-language header with an unknown language reverts to the default"""
        response = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE='sv')
        self.assertEqual(200, response.status_code)
        self.assertContains(response, '<html lang="en"', status_code=200)
