from io import StringIO
import csv

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now

from register.forms import CSV_FIELDS, BlacklistedNumberEditForm, WhitelistedNumberEditForm
from register.models import Blacklist, Whitelist, RegistrationCenter, Registration
from register.tests.base import LibyaTest
from register.tests.factories import WhitelistFactory, BlacklistFactory, \
    RegistrationCenterFactory, RegistrationFactory
from register.tests.test_center_csv import CenterFileTestMixin
from libya_elections.phone_numbers import get_random_phone_number, format_phone_number
from libya_elections.tests.utils import ResponseCheckerMixin
from libya_site.tests.factories import UserFactory, DEFAULT_USER_PASSWORD
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
        file_content = ("""%s\r\n%s\n \n%s\r%s""" % (
            punctuated_numbers[0],
            punctuated_numbers[1],
            punctuated_numbers[2],
            punctuated_numbers[3],
        )).encode()
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
        file_content = number.encode()
        blackwhitelist_file = ContentFile(file_content, name='bw.txt')
        data = {'import_file': blackwhitelist_file}
        rsp = self.client.post(self.url, data=data)
        # Assert that we redirect
        self.assertEqual(302, rsp.status_code)
        bwlist = self.model.objects.values_list('phone_number', flat=True)
        self.assertEqual(len(bwlist), 1)
        self.assertIn(number, bwlist)

    def test_import_number_cant_start_with_2180(self):
        "Ensures that the number doesn't start with 2180"
        number = '218091234123'
        file_content = number.encode()
        blackwhitelist_file = ContentFile(file_content, name='bw.txt')
        data = {'import_file': blackwhitelist_file}
        rsp = self.client.post(self.url, data=data, follow=True)
        self.assertEqual(200, rsp.status_code)
        bwlist = self.model.objects.values_list('phone_number', flat=True)
        self.assertEqual(len(bwlist), 0)
        self.assertContains(rsp, 'Numbers on these lines not imported because '
                            'they are not valid phone numbers: 1.')


class TestImportBlacklistView(ImportBlackWhitelistViewMixin, LibyaTest):
    """Exercise uploading a list of blacklisted numbers"""
    def setUp(self):
        self.model = Blacklist
        self.permissions = ('add_blacklist', 'browse_blacklist')
        self.url = reverse('blacklisted-numbers-upload')
        self.factory = BlacklistFactory

        super(TestImportBlacklistView, self).setUp()


class TestImportWhitelistView(ImportBlackWhitelistViewMixin, LibyaTest):
    """Exercise uploading a list of whitelisted numbers"""
    def setUp(self):
        self.permissions = ('add_whitelist', 'browse_whitelist')
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
        form = self.form(data={'phone_number': punctuated_number})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['phone_number'], number)

    def test_add_dupe_shows_form_error(self):
        number = get_random_phone_number()
        self.factory(phone_number=number)
        form = self.form(data={'phone_number': number})
        self.assertFalse(form.is_valid())
        self.assertIn('Duplicate value for phone number', list(form.errors.values())[0])

    def test_phone_number_cant_start_with_2180(self):
        "Ensures the local prefix '0' isn't accidentally included in the phone number"
        number = '218091234124'
        form = self.form(data={'phone_number': number})
        self.assertFalse(form.is_valid())
        self.assertIn('Please enter a valid phone number', list(form.errors.values())[0][0])


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
        self.assertIn(bl.phone_number, rsp.content.decode())


class WhitelistDownload(StaffUserMixin, ResponseCheckerMixin, TestCase):
    permissions = ['read_whitelist']
    model = Whitelist

    def test_download_whitelist_file(self):
        wl = WhitelistFactory()
        rsp = self.client.get(reverse('whitelisted-numbers-download'))
        self.assertOK(rsp)
        self.assertIn(wl.phone_number, rsp.content.decode())


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
        self.assertIn('Are you sure you want to delete all 3', rsp.content.decode())

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
        self.assertIn('Are you sure you want to delete all 3', rsp.content.decode())

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
        self.assertIn('Are you sure you want to delete all 3', rsp.content.decode())

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


class TestRegistrationRead(StaffUserMixin, ResponseCheckerMixin, TestCase):
    """Test the read-registration view"""
    permissions = ['read_registration']
    model = Registration

    def test_no_server_error_if_citizen_is_missing(self):
        """A missing citizen can cause a DoesNotExist error. Be sure to catch it."""
        # create registration with a missing citizen
        registration = RegistrationFactory(citizen__missing=now())
        url = reverse('read_registration', kwargs={'pk': registration.pk})
        response = self.client.get(url)
        self.assertContains(response, registration.registration_center.center_id)


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
                if should_offer_delete:
                    self.assertContains(response, delete_url)
                else:
                    self.assertNotContains(response, delete_url)

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
        reader = csv.reader(StringIO(rsp.content.decode()))
        for i, field in enumerate(next(reader)):
            # check the header row
            self.assertEqual(field, CSV_FIELDS[i])
        for row in reader:
            # check each row against the DB values
            self.assertNotIn('None', str(row))
            center_id = row[0]
            center = RegistrationCenter.objects.get(center_id=center_id)
            for i, field in enumerate(CSV_FIELDS):
                # center_type is special because it is an integer in the DB, but a string in the CSV
                if field == 'center_type':
                    db_field_as_str = center.get_center_type_display()
                else:
                    db_field_as_str = str(getattr(center, field))
                if db_field_as_str == 'None':
                    db_field_as_str = ''
                self.assertEqual(row[i], db_field_as_str)


class RegistrationSearchTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.staff_user = UserFactory()
        cls.staff_user.is_staff = True
        cls.staff_user.save()
        # give this user permission to browse
        ct = ContentType.objects.get_for_model(Registration)
        perm_codename = 'browse_registration'
        perm = Permission.objects.get(content_type=ct, codename=perm_codename)
        cls.staff_user.user_permissions.add(perm)
        # create 2 registrations, one that we expect to find and one that we expect not to find
        cls.nid_we_should_find = 200000000001
        cls.phone_we_should_find = '218900000002'
        cls.nid_we_should_not_find = 200000000003
        cls.phone_we_should_not_find = '218000000004'
        cls.nonexistent_nid = 200000000005
        cls.nonexistent_phone = '218900000006'
        cls.present_reg = RegistrationFactory(
            archive_time=None,
            citizen__national_id=cls.nid_we_should_find,
            sms__from_number=cls.phone_we_should_find)
        cls.absent_reg = RegistrationFactory(
            archive_time=None,
            citizen__national_id=cls.nid_we_should_not_find,
            sms__from_number=cls.phone_we_should_not_find)

    def setUp(self):
        assert self.client.login(username=self.staff_user.username, password=DEFAULT_USER_PASSWORD)
        self.browse_url = reverse('browse_registrations')

    def test_search_finds_national_id(self):
        rsp = self.client.get(self.browse_url, data={'q': self.nid_we_should_find})
        self.assertIn(self.present_reg, rsp.context['object_list'])
        self.assertNotIn(self.absent_reg, rsp.context['object_list'])

    def test_search_finds_phone_number(self):
        rsp = self.client.get(self.browse_url, data={'q': self.phone_we_should_find})
        self.assertIn(self.present_reg, rsp.context['object_list'])
        self.assertNotIn(self.absent_reg, rsp.context['object_list'])

    def test_search_strips_whitespace_national_id(self):
        rsp = self.client.get(self.browse_url, data={'q': ' %s ' % self.nid_we_should_find})
        self.assertIn(self.present_reg, rsp.context['object_list'])
        self.assertNotIn(self.absent_reg, rsp.context['object_list'])

    def test_search_strips_whitespace_phone_number(self):
        rsp = self.client.get(self.browse_url, data={'q': ' %s ' % self.phone_we_should_find})
        self.assertIn(self.present_reg, rsp.context['object_list'])
        self.assertNotIn(self.absent_reg, rsp.context['object_list'])

    def test_empty_search_result(self):
        rsp = self.client.get(self.browse_url, data={'q': self.nonexistent_nid})
        self.assertEqual(list(rsp.context['object_list']), [])

        rsp = self.client.get(self.browse_url, data={'q': self.nonexistent_phone})
        self.assertEqual(list(rsp.context['object_list']), [])

    def test_not_a_valid_nid_or_phone(self):
        rsp = self.client.get(self.browse_url, data={'q': '1234'})
        self.assertEqual(list(rsp.context['object_list']), [])

    def test_search_for_nondigit(self):
        search_term = self.present_reg.citizen.first_name
        rsp = self.client.get(self.browse_url, data={'q': search_term})
        self.assertIn(self.present_reg, rsp.context['object_list'])
        self.assertNotIn(self.absent_reg, rsp.context['object_list'])
