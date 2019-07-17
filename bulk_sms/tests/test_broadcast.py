from unittest.mock import patch, Mock

from django.conf import settings
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from bulk_sms.models import Broadcast, Batch
from bulk_sms.tests.factories import BroadcastFactory
from libya_elections.tests.utils import ResponseCheckerMixin
from libya_site.tests.factories import UserFactory
from register.tests.factories import RegistrationCenterFactory
from staff.tests.base import StaffUserMixin


class BroadcastHelper(StaffUserMixin):
    permissions = ['add_broadcast', 'browse_broadcast', 'read_broadcast', 'approve_broadcast']

    def setUp(self):
        self.staff_user = self.create_staff_user()
        self.login(self.staff_user)

    def create_staff_user(self):
        user = UserFactory(username=self.username, email=self.email,
                           password=self.password)
        user.is_staff = True
        user.save()
        return user

    @staticmethod
    def add_permissions(user, permissions):
        for perm in permissions:
            user.user_permissions.add(Permission.objects.get(codename=perm))

    @staticmethod
    def remove_permissions(user, permissions):
        for perm in permissions:
            user.user_permissions.remove(Permission.objects.get(codename=perm))


class BroadcastBreadTest(ResponseCheckerMixin, BroadcastHelper, TestCase):
    def setUp(self):
        super(BroadcastBreadTest, self).setUp()
        self.broadcast = BroadcastFactory(message='test')
        self.add_via_simple_form_url = reverse('add_broadcast')
        self.add_via_csv_upload = reverse('upload_broadcast')
        self.approve_url = reverse('approve_reject_broadcast',
                                   kwargs={'broadcast_id': self.broadcast.id})

    def test_browse_broadcasts(self):
        perms = ['browse_broadcast']
        # user with browse_broadcast permission can browse
        self.add_permissions(self.staff_user, perms)
        response = self.client.get(reverse('browse_broadcasts'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, template_name='bulk_sms/broadcast_browse.html')
        # users without the browse_broadcast permission can't get to that page
        self.remove_permissions(self.staff_user, perms)
        self.assertForbidden(self.client.get(reverse('browse_broadcasts')))

    def test_read_broadcast(self):
        broadcast = BroadcastFactory()
        perms = ['read_broadcast']
        # user with read_broadcast permission can browse
        self.add_permissions(self.staff_user, perms)
        response = self.client.get(reverse('read_broadcast', kwargs={'pk': broadcast.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response,
                                template_name='bulk_sms/broadcast_approve_reject.html')
        # users without the read_broadcast permission can't get to that page
        self.remove_permissions(self.staff_user, perms)
        self.assertForbidden(self.client.get(reverse('read_broadcast',
                                                     kwargs={'pk': broadcast.id})))

    def test_add_broadcast_via_simple_form(self):
        perms = ['add_broadcast']
        data = {'audience': 'staff', 'message': 'test broadcasting message'}
        broadcast_count = Broadcast.objects.count()
        # users with add_broadcast permission can view the add broadcast form
        self.add_permissions(self.staff_user, perms)
        response = self.client.get(self.add_via_simple_form_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response,
                                template_name="bulk_sms/broadcast_add_via_form.html")
        # users with add_broadcast permission can create broadcasts
        response = self.client.post(self.add_via_simple_form_url, data=data)
        self.assertEqual(response.status_code, 302)
        new_broadcast_count = Broadcast.objects.count()
        self.assertEqual(broadcast_count + 1, new_broadcast_count)
        # users without add_broadcast permission can't create broadcasts
        self.remove_permissions(self.staff_user, perms)
        self.assertForbidden(self.client.post(self.add_via_simple_form_url, data=data))

    def test_add_broadcast_via_csv_upload(self):
        perms = ['add_broadcast']
        mock_file = Mock()
        mock_file.read.return_value = "218911234567,the quick brown fox etc.\n"
        mock_file.name = 'foo.csv'
        data = {'name': 'test_batch', 'description': 'test broadcasting description',
                'csv': mock_file}
        broadcast_count = Broadcast.objects.count()
        # users with add_broadcast permission can view the add broadcast form
        self.add_permissions(self.staff_user, perms)
        response = self.client.get(self.add_via_csv_upload)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, template_name="bulk_sms/broadcast_add_via_csv.html")
        # users with add_broadcast permission can create broadcasts
        response = self.client.post(self.add_via_csv_upload, data=data)
        self.assertEqual(response.status_code, 302)
        new_broadcast_count = Broadcast.objects.count()
        self.assertEqual(broadcast_count + 1, new_broadcast_count)
        # users without add_broadcast permission can't create broadcasts
        self.remove_permissions(self.staff_user, perms)
        self.assertForbidden(self.client.post(self.add_via_csv_upload, data=data))

    def test_center_required(self):
        # center is a required field when creating a broadcast for a single
        # center.
        perms = ['add_broadcast']
        data = {'audience': 'single_center', 'message': 'test broadcasting message'}
        broadcast_count = Broadcast.objects.count()
        center = RegistrationCenterFactory()
        # form will have errors if the center field was not filled.
        self.add_permissions(self.staff_user, perms)
        response = self.client.post(self.add_via_simple_form_url, data=data)
        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response,
                                template_name="bulk_sms/broadcast_add_via_form.html")
        errors = response.context['form'].errors
        self.assertEqual(len(errors), 1)
        # submitting all required fields
        data['center'] = center.id
        response = self.client.post(self.add_via_simple_form_url, data=data)
        self.assertEqual(response.status_code, 302)
        new_broadcast_count = Broadcast.objects.count()
        self.assertEqual(broadcast_count + 1, new_broadcast_count)

    @patch('bulk_sms.tasks.approve_broadcast.delay', autospec=True)
    def test_approve_broadcast(self, approve_task):
        # broadcasts can be approved by users with the `approve_broadcast` permission.
        # approving a broadcast fires up the `approve_broadcast` task.
        perms = ['approve_broadcast']
        data = {'approve': True}
        # user does not have permission to approve broadcasts
        response = self.client.post(self.approve_url, data=data)
        self.assertEqual(response.status_code, 403)
        # give user permission to approve broadcasts
        self.add_permissions(self.staff_user, perms)
        self.client.post(self.approve_url, data=data)
        # approve_broadcast task was fired
        approve_task.assert_called_once_with(self.broadcast.id)

    def test_reject_broadcast(self):
        # broadcasts can be rejected.
        self.assertEqual(self.broadcast.batch.status, Batch.PENDING)
        perms = ['approve_broadcast']
        data = {'reject': True}
        # user does not have permission to approve broadcasts
        response = self.client.post(self.approve_url, data=data)
        self.assertEqual(response.status_code, 403)
        # give user permission to approve broadcasts
        self.add_permissions(self.staff_user, perms)
        self.client.post(self.approve_url, data=data)
        broadcast = Broadcast.objects.get(pk=self.broadcast.id)
        self.assertEqual(broadcast.batch.status, Batch.REJECTED)
        self.assertEqual(broadcast.reviewed_by, self.staff_user)
        # an approved message can be unapproved
        broadcast.batch.status = Batch.APPROVED
        broadcast.batch.save()
        self.client.post(self.approve_url, data=data)
        broadcast = Broadcast.objects.get(pk=self.broadcast.id)
        self.assertEqual(broadcast.batch.status, Batch.REJECTED)
        self.assertEqual(broadcast.reviewed_by, self.staff_user)


class BroadcastModelTest(BroadcastHelper, TestCase):
    def setUp(self):
        super(BroadcastModelTest, self).setUp()
        self.broadcast = Broadcast.objects.create(created_by=self.staff_user, message='test')

    def test_batch(self):
        # a batch is created the first time you save an instance.
        self.assertIsInstance(self.broadcast.batch, Batch)

    def test_status(self):
        # the status for a broadcast is the same as that of the batch associated with
        # it.
        self.assertEqual(self.broadcast.batch.status, Batch.PENDING)
        self.assertEqual(self.broadcast.status, _("Pending Approval"))
        self.broadcast.batch.status = Batch.APPROVED
        self.assertEqual(self.broadcast.status, self.broadcast.batch.get_status_display())

    def test_get_messages(self):
        # get_messages() yields tuples (phone_number, message, shortcode) for each individual
        # in the audience.
        # broadcast directed to staff users only (audience defaults to STAFF_ONLY)
        broadcast = self.broadcast
        broadcasting_message = "Broadcast for staff"
        broadcast.message = broadcasting_message
        with patch.object(Broadcast, 'get_numbers_for_staff') as staff_numbers:
            phone_numbers = ['1', '2', '3']
            staff_numbers.return_value = phone_numbers
            messages = [message for message in self.broadcast.get_messages()]
            staff_numbers.assert_called_once_with()
            for index, (phone_number, message, shortcode) in enumerate(messages):
                self.assertEqual(phone_number, phone_numbers[index])
                self.assertEqual(message, broadcasting_message)
                # STAFF_ONLY message, so from_shortcode should be REPORTS_SHORT_CODE
                self.assertEqual(shortcode, settings.REPORTS_SHORT_CODE)

        # broadcast directed to all registrants
        broadcasting_message = "Broadcast for all registrants"
        broadcast.audience = Broadcast.ALL_REGISTRANTS
        broadcast.message = broadcasting_message
        with patch.object(Broadcast, 'get_numbers_for_all_centers') as all_registrants:
            phone_numbers = ['1', '2', '3']
            all_registrants.return_value = phone_numbers
            messages = [message for message in self.broadcast.get_messages()]
            all_registrants.assert_called_once_with()
            for index, (phone_number, message, shortcode) in enumerate(messages):
                self.assertEqual(phone_number, phone_numbers[index])
                self.assertEqual(message, broadcasting_message)
                # ALL_REGISTRANTS message, so from_shortcode should be None
                # (which will trigger default shortcode to be used)
                self.assertEqual(shortcode, None)

        # broadcasting message for a single center
        broadcasting_message = "Broadcast for single center"
        broadcast.audience = Broadcast.SINGLE_CENTER
        broadcast.message = broadcasting_message
        with patch.object(Broadcast, 'get_numbers_for_single_center') as single_center:
            phone_numbers = ['1', '2', '3']
            single_center.return_value = phone_numbers
            messages = [message for message in self.broadcast.get_messages()]
            single_center.assert_called_once_with()
            for index, (phone_number, message, shortcode) in enumerate(messages):
                self.assertEqual(phone_number, phone_numbers[index])
                self.assertEqual(message, broadcasting_message)
                # SINGLE_CENTER message, so from_shortcode should be None
                # (which will trigger default shortcode to be used)
                self.assertEqual(shortcode, None)
