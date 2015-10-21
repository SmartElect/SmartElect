from django.core.urlresolvers import reverse
from django.test import TestCase

from libya_elections.tests.utils import ResponseCheckerMixin
from .base import StaffUserMixin


class DjangoAdminPermissions(ResponseCheckerMixin, StaffUserMixin, TestCase):

    def setUp(self):
        super(DjangoAdminPermissions, self).setUp()
        self.admin_url = reverse('admin:index')

    def test_unauthenticated_user(self):
        """Unauthenticated user should be redirected to login."""
        self.client.logout()
        response = self.client.get(self.admin_url)
        self.assertRedirectsToLogin(response, admin_login=True)

    def test_nonstaff_user(self):
        """Nonstaff user -> 403."""
        self.user.is_staff = False
        self.user.save()
        response = self.client.get(self.admin_url)
        self.assertForbidden(response)

    def test_staff_nonsuperuser(self):
        """Staff user, but not superuser -> 403."""
        response = self.client.get(self.admin_url)
        self.assertForbidden(response)

    def test_nonstaff_superuser(self):
        """Superuser, but not staff -> 403.

        This is likely a misconfiguration, as nonstaff superusers have the same privileges as a
        public user.
        """
        self.user.is_staff = False
        self.user.is_superuser = True
        self.user.save()
        response = self.client.get(self.admin_url)
        self.assertForbidden(response)

    def test_superuser(self):
        """Superuser and staff, but not staff -> 200."""
        self.user.is_superuser = True
        self.user.save()
        response = self.client.get(self.admin_url)
        self.assertOK(response)
