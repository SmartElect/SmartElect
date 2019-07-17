# -*- coding: utf-8 -*-
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from bulk_sms.models import Batch, Broadcast
from bulk_sms.tests.factories import BatchFactory
from libya_elections.tests.utils import ResponseCheckerMixin
from libya_site.tests.factories import UserFactory
from register.tests.base import LibyaTest

CSV_DATA = """218923456789,A message
218923456790,.نآسف، مرحلة التسجيل عن طريق الرسائل النصية ليست متاحة
""".encode()


class BulkUploadViewTest(ResponseCheckerMixin, LibyaTest):

    def setUp(self):
        self.home_url = reverse('upload_broadcast')
        self.staff_user = UserFactory(username='joestaff', password='puppy')
        self.staff_user.is_staff = True
        self.staff_user.user_permissions.add(Permission.objects.get(codename='add_broadcast'))
        self.staff_user.user_permissions.add(Permission.objects.get(codename='read_broadcast'))
        self.staff_user.user_permissions.add(Permission.objects.get(codename='browse_broadcast'))
        self.staff_user.user_permissions.add(Permission.objects.get(codename='approve_broadcast'))
        self.staff_user.save()
        self.client.login(username='joestaff', password='puppy')

    def test_get_home_view_no_user(self):
        # get home view, not_logged_in -> redirects to login
        self.client.logout()
        self.assertRedirectsToLogin(self.client.get(self.home_url))

    def test_get_home_view_not_staff(self):
        # get view not_staff -> 403
        self.client.logout()
        self.user = UserFactory(username='joe', password='puppy')
        self.client.login(username='joe', password='puppy')
        self.assertForbidden(self.client.get(self.home_url))

    def test_get_home_view_staff(self):
        # get view staff -> shows form
        rsp = self.client.get(self.home_url)
        self.assertEqual(200, rsp.status_code)
        self.assertIn('form', rsp.context)

    def test_post_upload_invalid(self):
        # post view invalid -> shows form
        data = {}
        rsp = self.client.post(self.home_url, data=data)
        self.assertEqual(200, rsp.status_code)
        self.assertIn('form', rsp.context)
        self.assertTrue(rsp.context['form'].errors)

    def test_post_upload_valid(self):
        # post view valid -> no form, contains status about batch
        f = SimpleUploadedFile("batch_test.csv", CSV_DATA)
        data = {'name': 'A name', 'csv': f, 'message': 'Upload'}
        rsp = self.client.post(reverse('upload_broadcast'), data=data, follow=True)
        self.assertNotIn('form', rsp.context)
        self.assertContains(rsp, 'Messages are uploading in the background')

    def test_uploaded_broadcast_same_user_cant_review(self):
        # uploaded batch, same user -> can't approve/reject
        batch = BatchFactory(status=Batch.PENDING, created_by=self.staff_user)
        BatchFactory(status=Batch.PENDING, created_by=self.staff_user, deleted=True)
        broadcast = Broadcast.objects.create(
            created_by=batch.created_by,
            batch=batch,
            audience=Broadcast.CUSTOM,
            message=batch.description
        )
        # can see detail page
        rsp = self.client.get(reverse('read_broadcast', kwargs=dict(pk=broadcast.id)))
        self.assertEqual(rsp.status_code, 200)
        self.assertContains(rsp, 'Approve')
        self.assertContains(rsp, 'Reject')
        # can't approve broadcast
        kwargs = dict(broadcast_id=broadcast.id)
        review_url = reverse('approve_reject_broadcast', kwargs=kwargs)
        data = {'approve': True}
        rsp = self.client.post(review_url, data=data)
        self.assertRedirects(rsp, reverse('read_broadcast', kwargs=dict(pk=broadcast.id)))

    def test_uploaded_broadcast_different_user_can_review(self):
        # uploaded batch, different user -> approve/reject button
        batch = BatchFactory(status=Batch.PENDING)
        BatchFactory(status=Batch.PENDING, created_by=self.staff_user, deleted=True)
        broadcast = Broadcast.objects.create(
            created_by=batch.created_by,
            batch=batch,
            audience=Broadcast.CUSTOM,
            message=batch.description
        )
        # can see detail page
        rsp = self.client.get(reverse('read_broadcast', kwargs=dict(pk=broadcast.id)))
        self.assertEqual(rsp.status_code, 200)
        self.assertContains(rsp, 'Approve')
        self.assertContains(rsp, 'Reject')
        # they can see approve broadcast
        kwargs = dict(broadcast_id=broadcast.id)
        review_url = reverse('approve_reject_broadcast', kwargs=kwargs)
        data = {'approve': True}
        rsp = self.client.post(review_url, data=data, follow=True)
        self.assertEqual(200, rsp.status_code)
        self.assertContains(rsp, 'You have approved the broadcast.')

    def test_rejected_batch_get_home_view(self):
        # rejected batch, get home view -> show form
        BatchFactory(status=Batch.REJECTED)
        BatchFactory(status=Batch.PENDING, deleted=True)
        rsp = self.client.get(self.home_url)
        self.assertEqual(200, rsp.status_code)
        self.assertIn('form', rsp.context)

    def test_completed_batch_get_home_view(self):
        # completed batch, get home view -> show form
        BatchFactory(status=Batch.COMPLETED)
        BatchFactory(status=Batch.PENDING, deleted=True)
        rsp = self.client.get(self.home_url)
        self.assertEqual(200, rsp.status_code)
        self.assertIn('form', rsp.context)

    def test_can_reject_batch(self):
        batch = BatchFactory(status=Batch.APPROVED)
        broadcast = Broadcast.objects.create(
            created_by=batch.created_by,
            batch=batch,
            audience=Broadcast.CUSTOM,
            message=batch.description
        )
        review_url = reverse('approve_reject_broadcast', kwargs={'broadcast_id': broadcast.id})
        data = {'reject': True}
        self.client.post(review_url, data=data)
        self.assertEqual(Batch.objects.get(id=batch.id).status, Batch.REJECTED)
