from StringIO import StringIO

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.core.urlresolvers import reverse
from django.test import TestCase

from ..forms import CSV_FIELDS, BlacklistedNumberEditForm, WhitelistedNumberEditForm
from ..models import Blacklist, Whitelist, RegistrationCenter
from .base import LibyaTest
from .factories import WhitelistFactory, BlacklistFactory, RegistrationCenterFactory
from .test_center_csv import CenterFileTestMixin
from libya_elections.csv_utils import UnicodeReader
from libya_elections.phone_numbers import get_random_phone_number, format_phone_number
from libya_elections.tests.utils import ResponseCheckerMixin
from libya_site.tests.factories import UserFactory
from polling_reports.models import StaffPhone
from polling_reports.tests.factories import StaffPhoneFactory
from staff.tests.base import StaffUserMixin


class ImportBlackWhitelistViewMixin(StaffUserMixin, ResponseCheckerMixin):
    """Base class for TestImportBlacklistView and TestImportWhitelistView.

    This doesn't inherit from TestCase, so it isn't executed by itself.
    """
    def setUp(self):
        super(ImportBlackWhitelistViewMixin, self).setUp()
        # self.url = None
        # self.model = None
        # self.factory = None

    def test_staff_can_see_form(self):
        rsp = self.client.get(self.url, follow=False)
        form = rsp.context['form']
        self.assertNotIn('password', form.fields)
        self.assertIn('import_file', form.fields)

    def test_nonstaff_cant_see_form(self):
        self.client.logout()
        self.nonstaff_user = UserFactory(username='joe', password='puppy')
        self.client.login(username='joe', password='puppy')
        self.assertForbidden(self.client.get(self.url))

    def test_valid_form(self):
        # with all combinations of line endings (\r\n, \n, \r)
        numbers = [get_random_phone_number() for i in range(4)]
        punctuated_numbers = [format_phone_number(number)
                              for number in numbers]
        file_content = b"""%s\r\n%s\n \n%s\r%s""" % (
            punctuated_numbers[0],
            punctuated_numbers[1],
            punctuated_numbers[2],
            punctuated_numbers[3],
        )
        blackwhitelist_file = ContentFile(file_content, name='bw.txt')
        data = {'import_file': blackwhitelist_file}
        rsp = self.client.post(self.url, data=data)
        # Assert that we redirect
        self.assertEqual(302, rsp.status_code)
        bwlist = self.model.objects.values_list('phone_number', flat=True)
        for number in numbers:
            self.assertIn(number, bwlist)
        self.assertEqual(len(bwlist), 4)

    def test_import_number_twice_works(self):
        "Importing a number that is already in list shouldn't cause an error"
        number = get_random_phone_number()
        self.factory(phone_number=number)
        file_content = b"%s" % number
        blackwhitelist_file = ContentFile(file_content, name='bw.txt')
        data = {'import_file': blackwhitelist_file}
        rsp = self.client.post(self.url, data=data)
        # Assert that we redirect
        self.assertEqual(302, rsp.status_code)
        bwlist = self.model.objects.values_list('phone_number', flat=True)
        self.assertEqual(len(bwlist), 1)
        self.assertIn(number, bwlist)


class TestImportBlacklistView(ImportBlackWhitelistViewMixin, LibyaTest):
    """Exercise uploading a list of blacklisted numbers"""
    def setUp(self):
        self.model = Blacklist
        self.permissions = ('add_blacklist',)
        self.url = reverse('blacklisted-numbers-upload')
        self.factory = BlacklistFactory

        super(TestImportBlacklistView, self).setUp()


class TestImportWhitelistView(ImportBlackWhitelistViewMixin, LibyaTest):
    """Exercise uploading a list of whitelisted numbers"""
    def setUp(self):
        self.permissions = ('add_whitelist',)
        self.model = Whitelist
        self.url = reverse('whitelisted-numbers-upload')
        self.factory = WhitelistFactory

        super(TestImportWhitelistView, self).setUp()


class BlackWhitelistEditFormMixin(StaffUserMixin, ResponseCheckerMixin):
    """Base class for TestBlacklistChangeForm and TestWhitelistChangeForm.

    This doesn't inherit from TestCase, so it isn't executed by itself.
    """
    def setUp(self):
        super(BlackWhitelistEditFormMixin, self).setUp()
        # self.factory = None
        # self.form = None

    def test_cleans_phone_number(self):
        number = get_random_phone_number()
        punctuated_number = format_phone_number(number)
        f = self.form(data={'phone_number': punctuated_number})
        self.assertTrue(f.is_valid(), f.errors)
        self.assertEqual(f.cleaned_data['phone_number'], number)

    def test_add_dupe_shows_form_error(self):
        number = get_random_phone_number()
        self.factory(phone_number=number)
        f = self.form(data={'phone_number': number})
        self.assertFalse(f.is_valid())
        self.assertIn('Duplicate value for phone number', f.errors.values()[0])


class TestBlacklistChangeForm(BlackWhitelistEditFormMixin, TestCase):
    """Exercise Blacklist number editing"""
    def setUp(self):
        super(TestBlacklistChangeForm, self).setUp()
        self.factory = BlacklistFactory
        self.form = BlacklistedNumberEditForm


class TestWhitelistChangeForm(BlackWhitelistEditFormMixin, TestCase):
    """Exercise Whitelist number editing"""
    def setUp(self):
        super(TestWhitelistChangeForm, self).setUp()
        self.factory = WhitelistFactory
        self.form = WhitelistedNumberEditForm


class BlacklistDownload(StaffUserMixin, ResponseCheckerMixin, TestCase):
    permissions = ['read_blacklist']
    model = Blacklist

    def test_download_blacklist_file(self):
        bl = BlacklistFactory()
        rsp = self.client.get(reverse('blacklisted-numbers-download'))
        self.assertOK(rsp)
        self.assertIn(bl.phone_number, rsp.content)


class WhitelistDownload(StaffUserMixin, ResponseCheckerMixin, TestCase):
    permissions = ['read_whitelist']
    model = Whitelist

    def test_download_whitelist_file(self):
        wl = WhitelistFactory()
        rsp = self.client.get(reverse('whitelisted-numbers-download'))
        self.assertOK(rsp)
        self.assertIn(wl.phone_number, rsp.content)


class DeleteBlacklist(StaffUserMixin, ResponseCheckerMixin, TestCase):
    permissions = ['delete_blacklist', 'browse_blacklist']
    model = Blacklist

    def setUp(self):
        super(DeleteBlacklist, self).setUp()
        self.url = reverse('blacklisted-numbers-delete')
        BlacklistFactory.create_batch(size=3)

    def test_get_deleted_page(self):
        rsp = self.client.get(self.url)
        self.assertOK(rsp)
        self.assertIn('Are you sure you want to delete all 3', rsp.content)

    def test_post_deleted_page(self):
        rsp = self.client.post(self.url, data={'ok': True})
        self.assertRedirects(rsp, reverse('browse_blacklistednumbers'))
        self.assertEqual(Blacklist.objects.count(), 0)


class DeleteWhitelist(StaffUserMixin, ResponseCheckerMixin, TestCase):
    permissions = ['delete_whitelist', 'browse_whitelist']
    model = Whitelist

    def setUp(self):
        super(DeleteWhitelist, self).setUp()
        self.url = reverse('whitelisted-numbers-delete')
        WhitelistFactory.create_batch(size=3)

    def test_get_deleted_page(self):
        rsp = self.client.get(self.url)
        self.assertOK(rsp)
        self.assertIn('Are you sure you want to delete all 3', rsp.content)

    def test_post_deleted_page(self):
        rsp = self.client.post(self.url, data={'ok': True})
        self.assertRedirects(rsp, reverse('browse_whitelistednumbers'))
        self.assertEqual(Blacklist.objects.count(), 0)


class DeleteStaffPhone(StaffUserMixin, ResponseCheckerMixin, TestCase):
    permissions = ['delete_staffphone', 'browse_staffphone']
    model = StaffPhone

    def setUp(self):
        super(DeleteStaffPhone, self).setUp()
        self.url = reverse('staffphones-delete')
        StaffPhoneFactory.create_batch(size=3)

    def test_get_deleted_page(self):
        rsp = self.client.get(self.url)
        self.assertOK(rsp)
        self.assertIn('Are you sure you want to delete all 3', rsp.content)

    def test_post_deleted_page(self):
        rsp = self.client.post(self.url, data={'ok': True})
        self.assertRedirects(rsp, reverse('browse_staffphones'))
        self.assertEqual(StaffPhone.objects.count(), 0)


class TestDeleteAllCopyCenters(StaffUserMixin, ResponseCheckerMixin, TestCase):
    def setUp(self):
        super(TestDeleteAllCopyCenters, self).setUp()
        self.url = reverse('delete-all-copy-centers')

    def add_permission(self, codename):
        """add permission with codename"""
        permission = Permission.objects.get(codename=codename)
        self.user.user_permissions.add(permission)

    def test_permissions(self):
        """ensure permission required to access delete page"""
        # no permission, no delete-o
        self.assertForbidden(self.client.get(self.url))
        self.assertForbidden(self.client.post(self.url, data={'ok': True}))
        # Once you have permission, all is well.
        self.add_permission('delete_registrationcenter')
        # Also add browse so the redirect works
        self.add_permission('browse_registrationcenter')
        self.assertOK(self.client.get(self.url))
        response = self.client.post(self.url, data={'ok': True})
        self.assertRedirects(response, reverse('browse_registrationcenters'))
        # not logged in ==> redirect
        self.client.logout()
        self.assertRedirectsToLogin(self.client.get(self.url))

    def test_confirmation_page_shows_center_to_be_deleted(self):
        """Ensure user sees what's about to be deleted before it happens"""
        self.add_permission('delete_registrationcenter')
        self.add_permission('browse_registrationcenter')

        # Create some copy centers
        original = RegistrationCenterFactory()
        copies = [RegistrationCenterFactory(copy_of=original) for i in range(3)]
        self.assertEqual(RegistrationCenter.objects.all().count(), 4)

        response = self.client.get(self.url)
        self.assertOK(response)
        self.assertIn('copy_centers', response.context)

        context_copy_centers = sorted([center.id for center in response.context['copy_centers']])
        copies = sorted([center.id for center in copies])

        self.assertEqual(context_copy_centers, copies)

    def test_delete_actually_deletes(self):
        """Ensure delete works as advertised"""
        original = RegistrationCenterFactory()
        RegistrationCenterFactory(copy_of=original)
        self.assertEqual(RegistrationCenter.objects.all().count(), 2)

        self.add_permission('delete_registrationcenter')
        # Also add browse so the redirect works
        self.add_permission('browse_registrationcenter')
        response = self.client.post(self.url, data={'ok': True})
        self.assertRedirects(response, reverse('browse_registrationcenters'))

        centers = RegistrationCenter.objects.all()
        self.assertEqual(len(centers), 1)
        self.assertEqual(centers[0].id, original.id)


class TestRegistrationCenterDeleteLogic(StaffUserMixin, ResponseCheckerMixin, TestCase):
    """Ensure that centers with copies can't be deleted"""
    permissions = ['delete_registrationcenter', 'read_registrationcenter',
                   'change_registrationcenter', ]
    model = RegistrationCenter

    def setUp(self):
        super(TestRegistrationCenterDeleteLogic, self).setUp()

        self.original = RegistrationCenterFactory()
        self.copy = RegistrationCenterFactory(copy_of=self.original)
        self.ordinary = RegistrationCenterFactory()

    def test_read_and_edit_views_offer_delete_appropriately(self):
        """Ensure the Delete button is available in the read and edit views when appropriate"""
        for center, should_offer_delete in ((self.original, False), (self.copy, True),
                                            (self.ordinary, True),):
            for url_name in ('read_registrationcenter', 'edit_registrationcenter'):
                url = reverse(url_name, kwargs={'pk': center.id})
                response = self.client.get(url)

                delete_url = reverse('delete_registrationcenter', kwargs={'pk': center.id})

                self.assertEqual(delete_url in response.content, should_offer_delete)

    def test_delete_view_available_appropriately(self):
        """Ensure the Delete view can be accessed when appropriate"""
        for center, should_offer_delete in ((self.original, False), (self.copy, True),
                                            (self.ordinary, True),):
            delete_url = reverse('delete_registrationcenter', kwargs={'pk': center.id})

            response = self.client.get(delete_url)

            if should_offer_delete:
                self.assertOK(response)
            else:
                self.assertForbidden(response)


class CenterDownload(CenterFileTestMixin, StaffUserMixin, TestCase):
    permissions = ['read_registrationcenter']
    model = RegistrationCenter

    def setUp(self):
        super(CenterDownload, self).setUp()
        self.download_csv_url = reverse('download-centers-csv')

    def test_download_link_is_on_ecc_form(self):
        url = reverse('upload-centers-csv')
        # Need 'add registrationcenter' to get to the upload page
        content_type = ContentType.objects.get_for_model(self.model)
        self.user.user_permissions.add(Permission.objects.get(content_type=content_type,
                                                              codename='add_registrationcenter'))
        rsp = self.client.get(url)
        self.assertEqual(200, rsp.status_code)
        self.assertContains(rsp, self.download_csv_url)

    def test_download_csv_file(self):
        # upload the test CSV to get some data in the DB
        self.upload_csv()
        # Add one with null values
        rc_with_nones = RegistrationCenterFactory(name="Center with no center_lat or center_lon",
                                                  center_lat=None,
                                                  center_lon=None)
        self.assertEqual(rc_with_nones.center_lat, None)
        self.assertEqual(rc_with_nones.center_lon, None)

        # download the CSV file
        rsp = self.client.get(self.download_csv_url)
        self.assertEqual(200, rsp.status_code)
        reader = UnicodeReader(StringIO(rsp.content))
        for i, field in enumerate(reader.next()):
            # check the header row
            self.assertEqual(field, CSV_FIELDS[i])
        for row in reader:
            # check each row against the DB values
            self.assertNotIn('None', unicode(row))
            center_id = row[0]
            center = RegistrationCenter.objects.get(center_id=center_id)
            for i, field in enumerate(CSV_FIELDS):
                # center_type is special because it is an integer in the DB, but a string in the CSV
                if field == 'center_type':
                    db_field_as_str = center.get_center_type_display()
                else:
                    db_field_as_str = unicode(getattr(center, field))
                if db_field_as_str == 'None':
                    db_field_as_str = ''
                self.assertEqual(row[i], db_field_as_str)
