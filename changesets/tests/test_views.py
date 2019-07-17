from operator import attrgetter
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Group
from django.http.response import HttpResponseForbidden, HttpResponseBadRequest, HttpResponseBase, \
    HttpResponseNotAllowed
from django.test import TestCase
from django.urls import reverse

from changesets.views_uploadedcitizens import UploadedCitizenBrowse
from civil_registry.tests.factories import CitizenFactory
from libya_elections.tests.utils import assert_in_messages
from libya_site.tests.factories import UserFactory
from ..models import Changeset, CHANGE_CHANGESETS_GROUP, \
    APPROVE_CHANGESETS_GROUP, QUEUE_CHANGESETS_GROUP
from .factories import ChangesetFactory, ChangeRecordFactory
from register.tests.factories import RegistrationCenterFactory


OK = HttpResponseBase.status_code
BAD_REQUEST = HttpResponseBadRequest.status_code
FORBIDDEN = HttpResponseForbidden.status_code
NOT_ALLOWED = HttpResponseNotAllowed.status_code


class GroupsMixin(object):
    @classmethod
    def setUpTestData(cls):
        cls.change_group = Group.objects.get(name=CHANGE_CHANGESETS_GROUP)
        cls.approve_group = Group.objects.get(name=APPROVE_CHANGESETS_GROUP)
        cls.queue_group = Group.objects.get(name=QUEUE_CHANGESETS_GROUP)


class ViewPermissionTests(GroupsMixin, TestCase):
    def setUp(self):
        self.password = "PASSWORD"
        self.peon = UserFactory(password=self.password)
        self.changer = UserFactory(password=self.password)
        self.changer.groups.add(self.change_group)
        self.approver = UserFactory(password=self.password)
        self.approver.groups.add(self.approve_group)
        self.queuer = UserFactory(password=self.password)
        self.queuer.groups.add(self.queue_group)
        self.deleter = UserFactory(password=self.password)
        self.deleter.groups.add(self.change_group)

    def permitted(self, user):
        """Return True if user can visit self.url and not get a permission denied"""
        assert self.client.login(username=user.username, password=self.password)
        rsp = self.client.get(self.url)
        self.assertIn(rsp.status_code, (OK, FORBIDDEN))
        return rsp.status_code != FORBIDDEN

    def test_redirect_to_login(self):
        # When not logged in, users get redirected to login.
        url = reverse('browse_changesets')
        self.assertRedirects(self.client.get(url), reverse(settings.LOGIN_URL) + "?next=" + url)

        changeset = ChangesetFactory(status=Changeset.STATUS_NEW)

        for url in ('edit_changeset', 'read_changeset', 'delete_changeset'):
            url = reverse(url, kwargs={'pk': changeset.pk})
            self.assertRedirects(
                self.client.get(url), reverse(settings.LOGIN_URL) + "?next=" + url,
                msg_prefix="%s get did not redirect to login when not logged in" % url)
        for url in ('browse_changerecords', 'browse_uploadedcitizens', ):
            url = reverse(url)
            self.assertRedirects(
                self.client.get(url), reverse(settings.LOGIN_URL) + "?next=" + url,
                msg_prefix="%s get did not redirect to login when not logged in" % url)
        for url in ('approve_changeset', ):
            url = reverse(url, kwargs={'pk': changeset.pk})
            self.assertRedirects(
                self.client.post(url), reverse(settings.LOGIN_URL) + "?next=" + url,
                msg_prefix="%s post did not redirect to login when not logged in" % url)

    def test_get_list_view(self):
        # Need browse permission
        self.url = reverse('browse_changesets')
        self.assertFalse(self.permitted(self.peon))
        self.assertTrue(self.permitted(self.changer))
        self.assertTrue(self.permitted(self.approver))
        self.assertTrue(self.permitted(self.queuer))
        self.assertTrue(self.permitted(self.deleter))

    def test_get_edit_view(self):
        # Need edit permission
        changeset = ChangesetFactory(status=Changeset.STATUS_NEW)
        self.url = reverse('edit_changeset', kwargs={'pk': changeset.pk})
        self.assertFalse(self.permitted(self.peon))
        self.assertTrue(self.permitted(self.changer))
        self.assertTrue(self.permitted(self.approver))
        self.assertTrue(self.permitted(self.queuer))
        self.assertTrue(self.permitted(self.deleter))

    def test_get_view_view(self):
        # Need read permission
        changeset = ChangesetFactory(status=Changeset.STATUS_NEW)
        self.url = reverse('read_changeset', kwargs={'pk': changeset.pk})
        self.assertFalse(self.permitted(self.peon))
        self.assertTrue(self.permitted(self.changer))
        self.assertTrue(self.permitted(self.approver))
        self.assertTrue(self.permitted(self.queuer))
        self.assertTrue(self.permitted(self.deleter))

    def test_get_create_view(self):
        # Need add permission
        self.url = reverse('add_changeset')
        self.assertFalse(self.permitted(self.peon))
        self.assertTrue(self.permitted(self.changer))
        self.assertTrue(self.permitted(self.approver))
        self.assertTrue(self.permitted(self.queuer))
        self.assertTrue(self.permitted(self.deleter))

    def test_get_delete_view(self):
        changeset = ChangesetFactory(status=Changeset.STATUS_NEW)
        self.url = reverse('delete_changeset', kwargs={'pk': changeset.pk})
        self.assertFalse(self.permitted(self.peon))
        self.assertTrue(self.permitted(self.changer))
        self.assertTrue(self.permitted(self.approver))
        self.assertTrue(self.permitted(self.queuer))
        self.assertTrue(self.permitted(self.deleter))


class ListViewTest(GroupsMixin, TestCase):
    def setUp(self):
        self.password = "PASSWORD"
        user = UserFactory(password=self.password)
        user.groups.add(self.change_group)
        assert self.client.login(username=user.username, password=self.password)

    def test_list_view(self):
        changeset1 = ChangesetFactory(name="Edward Einsenstein")
        changeset2 = ChangesetFactory(name="Fritz Kumquat")
        url = reverse('browse_changesets')
        rsp = self.client.get(url)
        self.assertContains(rsp, changeset1.name)
        self.assertContains(rsp, changeset2.name)


class CreateViewTest(GroupsMixin, TestCase):
    def setUp(self):
        self.password = "PASSWORD"
        user = UserFactory(password=self.password)
        user.groups.add(self.change_group)
        assert self.client.login(username=user.username, password=self.password)

    def test_create_view(self):
        url = reverse('add_changeset')
        rsp = self.client.get(url)
        self.assertEqual(OK, rsp.status_code)
        self.center1 = RegistrationCenterFactory()
        self.center2 = RegistrationCenterFactory()
        data = {
            'name': 'My Changeset',
            'change': str(Changeset.CHANGE_CENTER),
            'how_to_select': str(Changeset.SELECT_CENTERS),
            'selected_centers_1': [str(self.center1.pk)],
            'target_center_1': str(self.center2.pk),
            'justification': 'Just because',
        }
        rsp = self.client.post(url, data=data, follow=True)
        self.assertRedirects(rsp, reverse('browse_changesets'))


class EditViewTest(GroupsMixin, TestCase):
    def setUp(self):
        self.password = "PASSWORD"
        user = UserFactory(password=self.password)
        user.groups.add(self.change_group)
        assert self.client.login(username=user.username, password=self.password)

    def test_edit_view(self):
        self.center1 = RegistrationCenterFactory()
        self.center2 = RegistrationCenterFactory()
        data = {
            'name': 'My Changeset',
            'change': str(Changeset.CHANGE_CENTER),
            'how_to_select': str(Changeset.SELECT_CENTERS),
            'selected_centers_1': [str(self.center1.pk)],
            'target_center_1': str(self.center2.pk),
            'justification': 'Just because',
        }
        changeset = ChangesetFactory(
            name=data['name'],
            change=Changeset.CHANGE_CENTER,
            how_to_select=Changeset.SELECT_CENTERS,
            target_center=self.center2,
            justification='Just because',
        )
        changeset.selected_centers.add(self.center1)
        url = reverse('edit_changeset', kwargs={'pk': changeset.pk})

        rsp = self.client.get(url)
        self.assertEqual(OK, rsp.status_code)

        data['name'] = 'My Edited Changeset'
        data['justification'] = 'My edited justficiation'

        rsp = self.client.post(url, data=data, follow=False)
        self.assertEqual(302, rsp.status_code)  # , msg=rsp.content.decode('utf-8'))
        self.assertRedirects(rsp, reverse('browse_changesets'))

        changeset = Changeset.objects.get()
        self.assertEqual(data['name'], changeset.name)
        self.assertEqual(data['justification'], changeset.justification)

    def test_edit_view_not_in_editable_state(self):
        changeset = ChangesetFactory(status=Changeset.STATUS_FAILED)
        url = reverse('edit_changeset', kwargs={'pk': changeset.pk})
        rsp = self.client.get(url)
        self.assertRedirects(rsp, reverse('read_changeset', kwargs=dict(pk=changeset.pk)))


class ViewViewTest(GroupsMixin, TestCase):
    def setUp(self):
        self.password = "PASSWORD"
        user = UserFactory(password=self.password)
        user.groups.add(self.change_group)
        assert self.client.login(username=user.username, password=self.password)

    def test_view_view(self):
        self.center1 = RegistrationCenterFactory(name='Centero Uno')
        # Try a non-ASCII center to exercise the view. See issue 1966:
        # https://github.com/hnec-vr/libya-elections/issues/1966
        self.center2 = RegistrationCenterFactory(name='Centre Tv\xe5')
        changeset = ChangesetFactory(
            name='My Changeset',
            change=Changeset.CHANGE_CENTER,
            how_to_select=Changeset.SELECT_CENTERS,
            target_center=self.center2,
            justification='Just because',
        )
        changeset.selected_centers.add(self.center1)
        changeset.selected_centers.add(self.center2)
        url = reverse('read_changeset', kwargs={'pk': changeset.pk})
        rsp = self.client.get(url)
        self.assertEqual(OK, rsp.status_code)
        self.assertContains(rsp, self.center1.center_id)
        self.assertContains(rsp, self.center2.center_id)
        self.assertContains(rsp, 'Just because')
        self.assertContains(rsp, 'My Changeset')


class ApproveViewTest(GroupsMixin, TestCase):
    def setUp(self):
        self.password = "PASSWORD"
        self.peon = UserFactory(password=self.password)
        self.changer = UserFactory(password=self.password)
        self.changer.groups.add(self.change_group)
        self.approver = UserFactory(password=self.password)
        self.approver.groups.add(self.approve_group)
        self.queuer = UserFactory(password=self.password)
        self.queuer.groups.add(self.queue_group)

        self.changeset = ChangesetFactory()
        self.url = reverse('approve_changeset', kwargs={'pk': self.changeset.pk})
        self.read_url = reverse('read_changeset', args=[self.changeset.pk])

    def login(self, user):
        assert self.client.login(username=user.username, password=self.password)

    def test_theres_no_get_view(self):
        self.login(self.approver)
        rsp = self.client.get(self.url)
        self.assertEqual(NOT_ALLOWED, rsp.status_code)

    def test_peon_cannot_approve(self):
        self.login(self.peon)
        rsp = self.client.post(self.url, data={'approve': True})
        self.assertEqual(FORBIDDEN, rsp.status_code)

    def test_changer_cannot_approve(self):
        self.login(self.changer)
        rsp = self.client.post(self.url, data={'approve': True})
        self.assertEqual(FORBIDDEN, rsp.status_code)

    def test_approver_can_approve(self):
        self.login(self.approver)
        rsp = self.client.post(self.url, data={'approve': True})
        self.assertRedirects(rsp, self.read_url)

    def test_queuer_cannot_approve(self):
        # Start privilege is not the same as approve privilege, necessarily
        self.login(self.queuer)
        rsp = self.client.post(self.url, data={'approve': True})
        self.assertEqual(FORBIDDEN, rsp.status_code)

    def test_cannot_approve_after_queueing(self):
        superuser = UserFactory(is_superuser=True, password=self.password)
        self.changeset.approve(self.approver)
        self.changeset.approve(superuser)
        self.changeset.status = Changeset.STATUS_QUEUED
        self.changeset.save()

        self.login(superuser)
        rsp = self.client.post(self.url, data={'approve': True})

        self.assertContains(rsp, "after the changeset has been started.", status_code=BAD_REQUEST)

    def test_cannot_revoke_approval_after_queueing(self):
        superuser = UserFactory(is_superuser=True, password=self.password)
        self.changeset.approve(self.approver)
        self.changeset.approve(superuser)
        self.changeset.status = Changeset.STATUS_QUEUED
        self.changeset.save()

        self.login(superuser)
        rsp = self.client.post(self.url, data={'revoke': True})

        self.assertContains(rsp, "after the changeset has been started.", status_code=BAD_REQUEST)

    def test_user_already_approved(self):
        self.login(self.approver)
        rsp = self.client.post(self.url, data={'approve': True})
        self.assertRedirects(rsp, self.read_url)
        self.login(self.approver)
        rsp = self.client.post(self.url, data={'approve': True}, follow=True)
        self.assertRedirects(rsp, self.read_url)
        assert_in_messages(rsp, "already approved")

    def test_revoke(self):
        self.changeset.approve(self.approver)
        self.login(self.approver)
        rsp = self.client.post(self.url, data={'revoke': True})
        self.assertEqual(0, self.changeset.number_of_approvals)
        self.assertRedirects(rsp, self.read_url)

    def test_revoke_by_non_approver(self):
        # you can't revoke if you didn't approve
        self.changeset.approvers.add(self.peon, self.queuer)
        self.login(self.approver)
        rsp = self.client.post(self.url, data={'revoke': True})
        self.assertEqual(2, self.changeset.number_of_approvals)
        assert_in_messages(rsp, "You did not approve")
        self.assertEqual(BAD_REQUEST, rsp.status_code)

    def test_queue(self):
        # any old approvals
        self.changeset.approvers.add(self.peon, self.approver)
        self.changeset.status = Changeset.STATUS_APPROVED
        self.changeset.save()
        self.login(self.queuer)
        with patch.object(Changeset, 'queue') as mock_queue:
            rsp = self.client.post(self.url, data={'queue': True})
        assert mock_queue.called
        # queue redirects to the view page
        self.assertRedirects(rsp, self.read_url)

    def test_queue_without_permission(self):
        # must have queue permission
        # any old approvals
        self.changeset.approvers.add(self.peon, self.approver)
        # A user with perms to visit the approval page but not to queue
        self.login(self.approver)
        with patch.object(Changeset, 'queue') as mock_queue:
            rsp = self.client.post(self.url, data={'queue': True})
        mock_queue.assert_not_called()
        self.assertEqual(FORBIDDEN, rsp.status_code)

    def test_queue_not_approved(self):
        # can't queue if not approved
        # only one approval
        self.changeset.approve(self.approver)
        self.login(self.queuer)
        with patch.object(Changeset, 'queue') as mock_queue:
            rsp = self.client.post(self.url, data={'queue': True})
        mock_queue.assert_not_called()
        self.assertEqual(BAD_REQUEST, rsp.status_code)

    def test_approve_view_without_expected_args(self):
        assert not self.changeset.has_been_queued()
        self.login(self.approver)
        rsp = self.client.post(self.url, data={'nonsense': True})
        self.assertEqual(BAD_REQUEST, rsp.status_code)


class DeleteViewTest(GroupsMixin, TestCase):
    def setUp(self):
        self.password = "PASSWORD"
        self.peon = UserFactory(password=self.password)
        self.deleter = UserFactory(password=self.password)
        self.deleter.groups.add(self.change_group)

        self.changeset = ChangesetFactory()
        self.url = reverse('delete_changeset', kwargs={'pk': self.changeset.pk})

    def login(self, user):
        assert self.client.login(username=user.username, password=self.password)

    def test_can_delete_with_permission(self):
        changeset_pk = self.changeset.pk
        self.login(self.deleter)
        rsp = self.client.post(self.url)
        self.assertRedirects(rsp, reverse('browse_changesets'))
        self.assertFalse(Changeset.objects.filter(pk=changeset_pk).exists())

    def test_cannot_delete_without_permission(self):
        self.login(self.peon)
        rsp = self.client.post(self.url)
        self.assertEqual(FORBIDDEN, rsp.status_code)

    def test_cannot_deleted_queued_changeset(self):
        self.changeset.status = Changeset.STATUS_EXECUTING
        self.changeset.save()
        redirect_url = reverse('read_changeset', kwargs=dict(pk=self.changeset.pk))
        self.login(self.deleter)
        rsp = self.client.get(self.url)
        self.assertRedirects(rsp, redirect_url)
        self.assertTrue(Changeset.objects.filter(pk=self.changeset.pk).exists())
        rsp = self.client.post(self.url)
        self.assertRedirects(rsp, redirect_url)
        self.assertTrue(Changeset.objects.filter(pk=self.changeset.pk).exists())


class CitizenListViewTest(GroupsMixin, TestCase):
    def setUp(self):
        self.password = "PASSWORD"
        user = UserFactory(password=self.password)
        user.groups.add(self.change_group)
        assert self.client.login(username=user.username, password=self.password)

    def test_view_view(self):
        self.center2 = RegistrationCenterFactory(name='Centra Dua')
        changeset = ChangesetFactory(
            name='My Changeset',
            change=Changeset.CHANGE_CENTER,
            how_to_select=Changeset.SELECT_UPLOADED_NIDS,
            target_center=self.center2,
            justification='Just because',
        )
        per_page = UploadedCitizenBrowse.paginate_by
        self.assertIsNotNone(per_page)
        citizens = [CitizenFactory() for i in range(per_page + 2)]
        changeset.selected_citizens.add(*citizens)
        citizens = sorted(citizens, key=attrgetter('national_id'))

        # Get citizens affected by this changeset, sorted ascending by national ID
        url = reverse('browse_uploadedcitizens') + "?changeset=%s&o=0" % changeset.pk
        rsp = self.client.get(url)
        self.assertEqual(OK, rsp.status_code)
        context = rsp.context
        object_list = context['object_list']
        self.assertLessEqual(len(object_list), per_page)
        # Should be on first page
        self.assertContains(rsp, citizens[0].national_id)
        self.assertContains(rsp, str(citizens[0]))
        # Last citizen ought to be on the next page
        self.assertNotContains(rsp, citizens[-1].national_id)
        self.assertNotContains(rsp, str(citizens[-1]))


class ChangesViewTest(GroupsMixin, TestCase):
    def setUp(self):
        self.password = "PASSWORD"
        user = UserFactory(password=self.password)
        user.groups.add(self.change_group)
        assert self.client.login(username=user.username, password=self.password)

    def test_changed_view_for_changeset(self):
        # include ?changeset=NNN and it limits to that changeset
        changeset = ChangesetFactory()
        change1 = ChangeRecordFactory(changeset=changeset, changed=True)
        change2 = ChangeRecordFactory(changeset=changeset, changed=False)
        change3 = ChangeRecordFactory(changed=True)
        rsp = self.client.get(reverse('browse_changerecords') + "?changeset=%s" % changeset.pk)
        self.assertEqual(OK, rsp.status_code)
        context = rsp.context
        object_list = context['object_list']
        self.assertIn(change1, object_list)
        self.assertIn(change2, object_list)
        self.assertNotIn(change3, object_list)

    def test_changed_view_for_all(self):
        # Leave out ?changeset= and it shows all changes
        changeset = ChangesetFactory()
        change1 = ChangeRecordFactory(changeset=changeset, changed=True)
        change2 = ChangeRecordFactory(changeset=changeset, changed=False)
        change3 = ChangeRecordFactory(changed=True)
        rsp = self.client.get(reverse('browse_changerecords'))
        self.assertEqual(OK, rsp.status_code)
        context = rsp.context
        object_list = context['object_list']
        self.assertIn(change1, object_list)
        self.assertIn(change2, object_list)
        self.assertIn(change3, object_list)
