# -*- coding: utf-8 -*-
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.urlresolvers import reverse

from bulk_sms.models import BulkMessage, Batch, Broadcast
from bulk_sms.tests.factories import BatchFactory
from libya_elections.tests.utils import ResponseCheckerMixin
from libya_site.tests.factories import UserFactory
from register.tests.base import LibyaTest

GOOD_CSV_DATA = """218123456789,A message

8821612340058,.نآسف، مرحلة التسجيل عن طريق الرسائل النصية ليست متاحة
"""

INVALID_PHONE_DATA = """5551212,A message
218123456789,.نآسف، مرحلة التسجيل عن طريق الرسائل النصية ليست متاحة
"""

BLANK_MESSAGE_DATA = """218123456789,
218123456790,A message
8821612340058,.نآسف، مرحلة التسجيل عن طريق الرسائل النصية ليست متاحة""
"""

FAILS_PARSING_DATA = """218123456789,A message,extra field
218123456790,.نآسف، مرحلة التسجيل عن طريق الرسائل النصية ليست متاحة
"""

LINE_ENDINGS = "218123456789,a\n" + \
               "8821612340058,b\r" + \
               "218123456790,c\r\n"

INVALID_CHARACTERS = "218123456789,\x8e"


class ValidateUploadTest(ResponseCheckerMixin, LibyaTest):

    def setUp(self):
        self.home_url = reverse('upload_broadcast')
        self.staff_user = UserFactory(username='joestaff', password='puppy')
        self.staff_user.is_staff = True
        self.staff_user.save()
        self.staff_user.user_permissions.add(Permission.objects.get(codename='add_broadcast'))
        self.staff_user.user_permissions.add(Permission.objects.get(codename='approve_broadcast'))
        self.client.login(username='joestaff', password='puppy')

    def test_valid_upload_creates_bulkmessages(self):
        f = SimpleUploadedFile('file.csv', GOOD_CSV_DATA)
        data = {'name': u'A name', 'csv': f}
        self.client.post(self.home_url, data=data, follow=True)
        self.assertEqual(BulkMessage.objects.count(), 2)

    def test_line_endings(self):
        f = SimpleUploadedFile('file.csv', LINE_ENDINGS)
        data = {'name': u'A name', 'csv': f}
        self.client.post(self.home_url, data=data, follow=True)
        self.assertEqual(BulkMessage.objects.count(), 3)

    def test_invalid_characters(self):
        f = SimpleUploadedFile('file.csv', INVALID_CHARACTERS)
        data = {'name': u'A name', 'csv': f}
        rsp = self.client.post(self.home_url, data=data, follow=True)
        form = rsp.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn(u'The uploaded file had invalid characters.', form['csv'].errors[0])
        self.assertEqual(BulkMessage.objects.count(), 0)

    def test_invalid_phone(self):
        f = SimpleUploadedFile('file.csv', INVALID_PHONE_DATA)
        data = {'name': u'A name', 'csv': f}
        rsp = self.client.post(self.home_url, data=data, follow=True)
        form = rsp.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn(u'Unable to parse number', form['csv'].errors[0])
        self.assertEqual(BulkMessage.objects.count(), 0)

    def test_blank_message(self):
        f = SimpleUploadedFile('file.csv', BLANK_MESSAGE_DATA)
        data = {'name': u'A name', 'csv': f}
        rsp = self.client.post(self.home_url, data=data, follow=True)
        form = rsp.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn(u'Message is blank', form['csv'].errors[0])
        self.assertEqual(BulkMessage.objects.count(), 0)

    def test_invalid_csv_structure(self):
        f = SimpleUploadedFile('file.csv', FAILS_PARSING_DATA)
        data = {'name': u'A name', 'csv': f}
        rsp = self.client.post(self.home_url, data=data, follow=True)
        form = rsp.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn(u'The row should only have the following columns', form['csv'].errors[0])
        self.assertEqual(BulkMessage.objects.count(), 0)

    def test_bulk_create(self):
        # we bulk create every 10000 records, so make sure we use a number
        # in between checkpoints to make sure we don't leave any strays
        f = SimpleUploadedFile('file.csv', GOOD_CSV_DATA * 11000)
        data = {'name': u'A name', 'csv': f}
        self.client.post(self.home_url, data=data, follow=True)
        self.assertEqual(BulkMessage.objects.count(), 22000)

    # Test permissions
    def test_no_perms_cant_see_home_page(self):
        self.staff_user.user_permissions.remove(Permission.objects.get(codename='add_broadcast'))
        self.staff_user.user_permissions.remove(
            Permission.objects.get(codename='approve_broadcast'))
        # logged in as regular staff user
        self.assertForbidden(self.client.get(self.home_url))

    def test_add_broadcast_perm_sees_detail_page_but_cant_review(self):
        self.staff_user.user_permissions.remove(
            Permission.objects.get(codename='approve_broadcast'))
        self.staff_user.user_permissions.add(Permission.objects.get(codename='read_broadcast'))
        batch = BatchFactory(status=Batch.PENDING)
        broadcast = Broadcast.objects.create(
            created_by=batch.created_by,
            batch=batch,
            audience=Broadcast.CUSTOM,
            message=batch.description
        )
        review_url = reverse('approve_reject_broadcast', kwargs=dict(broadcast_id=broadcast.id))
        # can see detail page
        rsp = self.client.get(reverse('read_broadcast', kwargs=dict(pk=broadcast.id)))
        self.assertEqual(200, rsp.status_code)
        # and can't manually go to review url
        rsp = self.client.post(review_url)
        self.assertEqual(403, rsp.status_code)

    def test_approve_perm_cant_directly_post_upload_form(self):
        self.staff_user.user_permissions.remove(Permission.objects.get(codename='add_broadcast'))
        self.staff_user.user_permissions.add(Permission.objects.get(codename='approve_broadcast'))
        f = SimpleUploadedFile('file.csv', GOOD_CSV_DATA)
        data = {'name': u'A name', 'csv': f}
        self.assertForbidden(self.client.post(reverse('upload_broadcast'), data=data))
        self.assertEqual(BulkMessage.objects.count(), 0)

    def test_user_with_both_permissions_can_upload(self):
        self.staff_user.user_permissions.add(Permission.objects.get(codename='add_broadcast'))
        self.staff_user.user_permissions.add(Permission.objects.get(codename='approve_broadcast'))
        rsp = self.client.get(reverse('upload_broadcast'))
        # can see upload form
        self.assertIn('form', rsp.context)
        f = SimpleUploadedFile('file.csv', GOOD_CSV_DATA)
        data = {'name': u'A name', 'csv': f}
        rsp = self.client.post(reverse('upload_broadcast'), data=data, follow=True)
        # and messages are uploaded
        self.assertEqual(BulkMessage.objects.count(), 2)

    def test_user_with_both_permissions_can_approve(self):
        self.staff_user.user_permissions.add(Permission.objects.get(codename='add_broadcast'))
        self.staff_user.user_permissions.add(Permission.objects.get(codename='approve_broadcast'))
        batch = BatchFactory(status=Batch.PENDING)
        broadcast = Broadcast.objects.create(
            created_by=batch.created_by,
            batch=batch,
            audience=Broadcast.CUSTOM,
            message=batch.description
        )
        kwargs = dict(broadcast_id=broadcast.id)
        review_url = reverse('approve_reject_broadcast', kwargs=kwargs)
        data = {'approve': True}
        rsp = self.client.post(review_url, data=data)
        self.assertEqual(302, rsp.status_code)
