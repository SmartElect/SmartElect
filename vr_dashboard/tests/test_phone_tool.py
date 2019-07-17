from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from libya_site.tests.factories import DEFAULT_USER_PASSWORD, UserFactory
from register.models import RegistrationCenter
from register.tests.factories import RegistrationCenterFactory
from vr_dashboard.forms import PhoneAndMessageQueryForm


class TestPhoneToolAuth(TestCase):

    def test_auth(self):
        paths = (
            reverse('vr_dashboard:phone-message-tool'),
            reverse('vr_dashboard:search-phones'),
            reverse('vr_dashboard:phone-history'),
            reverse('vr_dashboard:whitelist-phone'),
        )
        for path in paths:
            rsp = self.client.get(path)
            self.assertRedirects(rsp, reverse(settings.LOGIN_URL) + "?next=" + path,
                                 msg_prefix='Path %s not handled properly' % path)


class TestPhoneTool(TestCase):

    def setUp(self):
        self.staff_user = UserFactory()
        self.staff_user.is_staff = True
        self.staff_user.save()

        assert self.client.login(username=self.staff_user.username,
                                 password=DEFAULT_USER_PASSWORD)

        self.bad_center_id = 'abcd'
        self.bad_phone_number = 'abcd'

        self.good_center_id = RegistrationCenterFactory().center_id
        self.good_looking_center_id = self.good_center_id + 1  # until the next center is created
        self.assertFalse(
            RegistrationCenter.objects.filter(center_id=self.good_looking_center_id).exists()
        )

        # these will both get whitelisted by this test class
        self.good_phone_number_1 = 218900000106
        self.good_phone_number_2 = 218900000107

    def test_form_validation(self):
        # no args
        form = PhoneAndMessageQueryForm({
        })
        self.assertFalse(form.is_valid())

        # too many args
        form = PhoneAndMessageQueryForm({
            'center_id': self.good_center_id,
            'phone_number': self.good_phone_number_1
        })
        self.assertFalse(form.is_valid())

        # bad center id
        form = PhoneAndMessageQueryForm({
            'center_id': self.bad_center_id,
        })
        self.assertFalse(form.is_valid())

        # bad center id that looks good
        form = PhoneAndMessageQueryForm({
            'center_id': self.good_looking_center_id,
        })
        self.assertFalse(form.is_valid())

        # bad phone
        form = PhoneAndMessageQueryForm({
            'phone_number': self.bad_phone_number,
        })
        self.assertFalse(form.is_valid())

        # just right (center id)
        form = PhoneAndMessageQueryForm({
            'center_id': self.good_center_id,
        })
        self.assertTrue(form.is_valid())

        # just right (phone)
        form = PhoneAndMessageQueryForm({
            'phone_number': self.good_phone_number_1,
        })
        self.assertTrue(form.is_valid())

    def test_form_view(self):
        rsp = self.client.get(reverse('vr_dashboard:phone-message-tool'))
        self.assertEqual(200, rsp.status_code)

        rsp = self.client.post(reverse('vr_dashboard:phone-message-tool'), {
            'center_id': self.good_center_id
        })
        self.assertRedirects(
            rsp,
            reverse('vr_dashboard:search-phones') + '?center_id=%s' % self.good_center_id,
            target_status_code=404  # no phones for that center
        )

        rsp = self.client.post(reverse('vr_dashboard:phone-message-tool'), {
            'phone_number': self.good_phone_number_1
        })
        self.assertRedirects(
            rsp,
            reverse('vr_dashboard:phone-history') + '?phone=%s' % self.good_phone_number_1
        )

    def test_bad_args(self):
        """ Test what happens when bad data gets past the form, or the form is
        bypassed.
        """
        rsp = self.client.get(reverse('vr_dashboard:search-phones')
                              + '?phone=%s' % self.bad_phone_number)
        self.assertEqual(400, rsp.status_code)
        rsp = self.client.get(reverse('vr_dashboard:search-phones')
                              + '?center=%s' % self.bad_center_id)
        self.assertEqual(400, rsp.status_code)
        rsp = self.client.get(reverse('vr_dashboard:phone-history')
                              + '?phone=%s' % self.bad_phone_number)
        self.assertEqual(400, rsp.status_code)

    def test_whitelist(self):        # success, redirect to phone history
        rsp = self.client.post(reverse('vr_dashboard:whitelist-phone'), {
            'phone': self.good_phone_number_1
        })
        self.assertRedirects(
            rsp,
            reverse('vr_dashboard:phone-history') + '?phone=%s' % self.good_phone_number_1
        )

        # success, redirect to phone list
        rsp = self.client.post(reverse('vr_dashboard:whitelist-phone'), {
            'phone': self.good_phone_number_2,
            'center_id': self.good_center_id
        })
        self.assertRedirects(
            rsp,
            reverse('vr_dashboard:search-phones') + '?center_id=%s' % self.good_center_id,
            target_status_code=404  # no phones for that center
        )

        # failure

        rsp = self.client.post(reverse('vr_dashboard:whitelist-phone'), {
            'phone': self.good_phone_number_1,
            'center_id': self.bad_center_id
        })
        self.assertEqual(rsp.status_code, 400)
