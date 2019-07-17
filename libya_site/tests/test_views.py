# -*- coding: utf-8 -*-
from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils.timezone import now

from civil_registry.tests.factories import CitizenFactory
from libya_elections import constants
from libya_site.tests.factories import UserFactory
from register.tests.base import PAST_DAY, FUTURE_DAY
from register.tests.factories import RegistrationFactory
from text_messages.utils import get_message
from voting.tests.factories import ElectionFactory, RegistrationPeriodFactory


class TestHomeview(TestCase):
    def setUp(self):
        self.url = reverse('home')

    @override_settings(HIDE_PUBLIC_DASHBOARD=False)
    def test_home_redirects_to_national_stats(self):
        # Normally, the home page redirects to the national stats
        rsp = self.client.get(self.url)
        self.assertRedirects(
            rsp,
            reverse('vr_dashboard:national'),
            fetch_redirect_response=False,
            msg_prefix='Home did not redirect to national stats'
        )

    @override_settings(HIDE_PUBLIC_DASHBOARD=True)
    def test_home_redirects_to_check_registration(self):
        # When hiding the public dashboard, the home page redirects to check registration
        rsp = self.client.get(self.url)
        self.assertRedirects(
            rsp,
            reverse('check_registration'),
            fetch_redirect_response=False,
            msg_prefix='Home did not redirect to check_registration'
        )


@override_settings(LANGUAGE_CODE='en')
class TestCheckRegistrationPageView(TestCase):
    def setUp(self):
        self.url = reverse('check_registration')
        self.user = UserFactory(username='joe', password='puppy')
        self.client.login(username='joe', password='puppy')
        # captcha has 2 form fields, _0 is a key, _1 is the text entered by the user
        self.captcha = {'captcha_0': 'dummy', 'captcha_1': 'PASSED'}
        self.registration = RegistrationPeriodFactory(start_time=PAST_DAY, end_time=PAST_DAY)
        self.election = ElectionFactory(polling_start_time=FUTURE_DAY, polling_end_time=FUTURE_DAY)

    def test_login_required(self):
        # Not logged in - redirect to login page
        self.client.logout()
        rsp = self.client.get(self.url, follow=False)
        self.assertEqual(302, rsp.status_code)

    @override_settings(TEMPLATE_STRING_IF_INVALID='INVALID_TEMPLATE_STRING: %s')
    def test_get(self):
        # Get displays the form
        rsp = self.client.get(self.url)
        self.assertEqual(200, rsp.status_code)
        context = rsp.context
        self.assertIn('form', context)
        form = context['form']
        self.assertNotIn('INVALID_TEMPLATE_STRING', rsp.content.decode('utf-8'))
        # No errors
        self.assertFalse(form.errors)

    def test_invalid_form(self):
        # POST with invalid value just displays error
        data = {'national_id': '27', 'fbr_number': '1234'}
        rsp = self.client.post(self.url, data=data)
        self.assertEqual(200, rsp.status_code)
        context = rsp.context
        self.assertIn('form', context)
        form = context['form']
        self.assertTrue(form.errors)

    def test_invalid_national_ids(self):
        """
        Invalid nlid triggers a form error
        """
        for invalid_nid in ['not-a-number',
                            '1112223334445',  # too long
                            '300000000000']:  # too large
            data = {'national_id': invalid_nid, 'fbr_number': '1234'}
            data.update(self.captcha)
            rsp = self.client.post(self.url, data=data)
            self.assertEqual(200, rsp.status_code)
            form = rsp.context['form']
            self.assertTrue(form.errors)

    @patch('requests.get')
    def test_that_we_convert_nid_to_number(self, mock_get):
        # get_person_by_national_id requires a number, not a string. make sure
        # that we convert to a number (long) during cleaning
        nid = '111222333444'
        data = {'national_id': nid, 'fbr_number': '1234'}
        data.update(self.captcha)
        # make mock return a 404 code, which our code interprets as invalid_nid
        mock_get.return_value.status_code.return_value = 404
        # post request will 500 if nid isn't converted to long
        rsp = self.client.post(self.url, data=data)
        self.assertEqual(200, rsp.status_code)

    def test_blank_fbr_number(self):
        data = {
            'national_id': '123456789013',
            'fbr_number': '1234'
        }
        CitizenFactory(fbr_number=int(data['fbr_number']), national_id=int(data['national_id']))
        post_data = data.copy()
        post_data.update(self.captcha)
        post_data['fbr_number'] = ''
        rsp = self.client.post(self.url, data=post_data, follow=False)
        self.assertEqual(200, rsp.status_code)
        context = rsp.context
        self.assertIn('form', context)
        form = context['form']
        self.assertIn('fbr_number', form.errors)

    def test_no_such_citizen(self):
        data = {'national_id': '123456789012', 'fbr_number': '1234'}
        data.update(self.captcha)
        rsp = self.client.post(self.url, data=data)
        self.assertEqual(200, rsp.status_code)
        context = rsp.context
        self.assertIn('form', context)
        form = context['form']
        self.assertIn('national_id', form.errors)
        self.assertIn(get_message(constants.NID_INVALID).msg,
                      form.errors['national_id'])
        content = rsp.content.decode('utf-8')
        self.assertIn(get_message(constants.NID_INVALID).msg, content)

    def test_new_citizen(self):
        CitizenFactory(national_id=123456789012, fbr_number=1234)
        data = {'national_id': '123456789012', 'fbr_number': '1234'}
        data.update(self.captcha)
        rsp = self.client.post(self.url, data=data)
        self.assertEqual(200, rsp.status_code)
        context = rsp.context
        self.assertIn('citizen', context)
        self.assertNotIn('center', context)

    def test_registered_citizen(self):
        citizen = CitizenFactory(fbr_number=1234)
        registration = RegistrationFactory(citizen=citizen, archive_time=None)
        data = {'national_id': str(citizen.national_id), 'fbr_number': citizen.fbr_number}
        data.update(self.captcha)
        rsp = self.client.post(self.url, data=data)
        self.assertEqual(200, rsp.status_code)
        content = rsp.content.decode('utf-8')
        self.assertNotIn("is not registered", content)
        self.assertIn("is registered at", content)
        self.assertIn(registration.registration_center.name, content)

    def test_registration_archived(self):
        citizen = CitizenFactory(fbr_number=1234)
        registration = RegistrationFactory(citizen=citizen, archive_time=now())
        data = {'national_id': str(citizen.national_id), 'fbr_number': citizen.fbr_number}
        data.update(self.captcha)
        rsp = self.client.post(self.url, data=data)
        self.assertEqual(200, rsp.status_code)
        content = rsp.content.decode('utf-8')
        self.assertIn("is not registered", content)
        self.assertNotIn("is registered at", content)
        self.assertNotIn(registration.registration_center.name, content)

    def test_fbr_number_mismatch(self):
        citizen = CitizenFactory(fbr_number=1234)
        RegistrationFactory(citizen=citizen, archive_time=None)
        data = {'national_id': str(citizen.national_id), 'fbr_number': '2345678'}
        data.update(self.captcha)
        rsp = self.client.post(self.url, data=data)
        self.assertEqual(200, rsp.status_code)
        context = rsp.context
        self.assertIn('form', context)
        form = context['form']
        self.assertTrue(form.errors)
        content = rsp.content.decode('utf-8')
        self.assertIn(get_message(constants.FBRN_MISMATCH).msg, content)

    def test_missing_captcha_causes_failure(self):
        CitizenFactory(
            national_id=123456789012,
            fbr_number=1234
        )
        data = {'national_id': '123456789012', 'fbr_number': '1234'}
        # no captcha, so skip the call -> data.update(self.captcha)
        rsp = self.client.post(self.url, data=data)
        errors = rsp.context['form'].errors
        self.assertTrue(errors)
        self.assertTrue('captcha' in errors)

    def test_eastern_arabic_in_nid(self):
        """
        Query site should accept Eastern arabic numerals for national_id.
        """
        CitizenFactory(fbr_number=1234, national_id=123456789012)
        data = {'national_id': '١٢٣٤٥٦٧٨٩٠12', 'fbr_number': '1234'}
        data.update(self.captcha)
        rsp = self.client.post(self.url, data=data)
        self.assertEqual(200, rsp.status_code)
        context = rsp.context
        self.assertIn('citizen', context)

    def test_eastern_arabic_in_fbrn(self):
        """
        Query site should accept Eastern arabic numerals for FBRN.
        """
        CitizenFactory(fbr_number=1234, national_id=123456789012)
        data = {'national_id': '١٢٣٤٥٦٧٨٩٠12', 'fbr_number': '١٢34'}
        data.update(self.captcha)
        rsp = self.client.post(self.url, data=data)
        self.assertEqual(200, rsp.status_code)
        context = rsp.context
        self.assertIn('citizen', context)


class TestSiteRegistration(TestCase):

    def test_successful_site_registration(self):
        url = reverse('registration_register')
        data = {
            'username': 'foo',
            'password1': 'fake-password',
            'password2': 'fake-password',
            'email': 'foo@example.com',
        }
        rsp = self.client.post(url, data=data, follow=True)
        # registration is successful and they are redirected to a page telling
        # them to check their email
        self.assertContains(rsp, 'Check your email account')
