from unittest.mock import Mock

from django.contrib import admin
from django.test import TestCase

from register.admin import RegistrationCenterAdmin
from register.models import RegistrationCenter
from register.tests.factories import RegistrationCenterFactory


class RegistrationCenterAdminCopyCenterTest(TestCase):
    """Exercise various special properties of copy centers related to the admin pages"""
    def test_copy_center_is_readonly(self):
        """Ensure copy centers can't be changed except for deleted status"""
        original = RegistrationCenterFactory()
        copy = RegistrationCenterFactory(copy_of=original)
        center_admin = RegistrationCenterAdmin(RegistrationCenter, admin.site)
        fields = set(center_admin.get_fields(Mock(), obj=copy))
        readonly_fields = set(center_admin.get_readonly_fields(Mock(), obj=copy))
        readwrite_fields = list(fields - readonly_fields)
        self.assertEqual(readwrite_fields, ['deleted'])

    def test_copy_of_attr_is_readonly_when_editing(self):
        """Ensure the copy_of attr is readonly when editing"""
        center = RegistrationCenterFactory()
        center_admin = RegistrationCenterAdmin(RegistrationCenter, admin.site)
        self.assertIn('copy_of', center_admin.get_readonly_fields(Mock(), obj=center))

    def test_copy_of_attr_is_readwrite_when_creating(self):
        """Ensure the copy_of attr is editable when creating a new reg center"""
        center_admin = RegistrationCenterAdmin(RegistrationCenter, admin.site)
        self.assertNotIn('copy_of', center_admin.get_readonly_fields(Mock()))

    def test_ensure_copied_center_undeletable(self):
        """Ensure centers that have copies can't be deleted"""
        original = RegistrationCenterFactory()
        copy = RegistrationCenterFactory(copy_of=original)
        center_admin = RegistrationCenterAdmin(RegistrationCenter, admin.site)
        self.assertIn('deleted', center_admin.get_readonly_fields(Mock(), obj=original))

        # However, if the copy is soft deleted, then it's OK to delete the original
        copy.deleted = True
        copy.save()
        center_admin = RegistrationCenterAdmin(RegistrationCenter, admin.site)
        self.assertNotIn('deleted', center_admin.get_readonly_fields(Mock(), obj=original))
