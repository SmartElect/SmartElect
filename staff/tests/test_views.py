from httplib import FORBIDDEN
import os

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.urlresolvers import reverse
from django.test import TestCase, override_settings

from libya_site.tests.factories import UserFactory


class TestStaffView(TestCase):
    def setUp(self):
        self.password = 'puppy'
        self.user = UserFactory(username='joe', password=self.password)
        self.user.is_staff = True
        self.user.save()
        self.assertTrue(self.client.login(username=self.user.username, password=self.password))
        self.staff_url = reverse('staff')
        self.httptester_url = reverse('httptester-index')

    def test_non_production_setting_shows_httptester(self):
        """Only superusers can see the httptester URL"""
        self.user.is_superuser = True
        self.user.save()
        rsp = self.client.get(self.staff_url)
        self.assertContains(rsp, self.httptester_url)

    @override_settings(ENVIRONMENT='production')
    def test_production_settings_no_httptester(self):
        rsp = self.client.get(self.staff_url)
        self.assertNotContains(rsp, self.httptester_url)

    def test_rollgen_visible_for_superuser(self):
        """ensure superusers see the rollgen URL"""
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()
        self.client.logout()
        self.assertTrue(self.client.login(username=self.user.username, password=self.password))

        rsp = self.client.get(self.staff_url)
        self.assertContains(rsp, reverse('rollgen:overview'))

    def test_rollgen_visible_for_rollgen_group_member(self):
        """ensure staff users in the rollgen_view_job group see the rollgen URL in the staff view"""
        self.user.is_staff = True
        self.user.groups.add(Group.objects.get(name='rollgen_view_job'))
        self.user.save()
        self.client.logout()
        self.assertTrue(self.client.login(username=self.user.username, password=self.password))
        rsp = self.client.get(self.staff_url)
        self.assertContains(rsp, reverse('rollgen:overview'))

    def test_rollgen_not_visible_for_rollgen_group_nonmember(self):
        """ensure staff users not in the rollgen_view_job group don't see the rollgen URL"""
        rsp = self.client.get(self.staff_url)
        self.assertNotContains(rsp, reverse('rollgen:overview'))

    def test_staff_page_redirects_to_login_if_not_logged_in(self):
        self.client.logout()
        rsp = self.client.get(self.staff_url)
        self.assertRedirects(rsp, reverse(settings.LOGIN_URL) + "?next=" + self.staff_url)

    def test_staff_page_responds_403_for_non_staff(self):
        self.user.is_staff = False
        self.user.save()
        rsp = self.client.get(self.staff_url)
        self.assertEqual(FORBIDDEN, rsp.status_code)


class TestGitRevView(TestCase):
    def test_git_rev(self):
        # Just make sure it doesn't blow up and returns something
        # It should work no matter what the current directory is

        url = reverse('gitrev')
        try:
            old_dir = os.getcwd()
            os.chdir('/')
            rsp = self.client.get(url)
        finally:
            os.chdir(old_dir)
        self.assertEqual(200, rsp.status_code)
        text = rsp.content
        self.assertTrue(text)
