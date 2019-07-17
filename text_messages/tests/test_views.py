from django.conf import settings
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from libya_site.tests.factories import UserFactory
from text_messages.models import MessageText


class TextMessagesViewsTestCase(TestCase):
    def setUp(self):
        self.number = 397
        self.msg = MessageText.objects.create(
            number=self.number,
            msg_en="Message",
            msg_ar="Message (ar)",
            enhanced_en="Enh msg",
            enhanced_ar="Enh msg (ar)",
        )
        self.staff_user = UserFactory(username='joestaff', password='puppy')
        self.perm = Permission.objects.get(codename='change_messagetext')
        self.staff_user.user_permissions.add(self.perm)
        assert self.client.login(username='joestaff', password='puppy')
        self.list_url = reverse('message_list')
        self.change_url = reverse('message_update', args=[self.msg.pk])

    def test_get_permissions_okay(self):
        # User is logged in and has permissions, should be able to load views
        self.assertEqual(200, self.client.get(self.list_url).status_code)
        self.assertEqual(200, self.client.get(self.change_url).status_code)

    def test_get_permissions_not_okay(self):
        # User is logged in and does not have permissions, should not be able to load views
        self.staff_user.user_permissions.remove(self.perm)
        self.assertEqual(403, self.client.get(self.list_url).status_code)
        self.assertEqual(403, self.client.get(self.change_url).status_code)

    def test_not_logged_in_redirects_to_login(self):
        # User is not logged in, should get redirected to login page
        self.client.logout()
        for url in (self.list_url, self.change_url):
            self.assertRedirects(self.client.get(url), reverse(settings.LOGIN_URL) + "?next=" + url)
