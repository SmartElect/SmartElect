# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils.timezone import now

from civil_registry.tests.factories import CitizenFactory
from libya_elections.utils import get_permission_object_by_name, refresh_model
from libya_site.tests.factories import UserFactory

from .factories import ChangesetFactory, ChangeRecordFactory
from ..exceptions import NotPermittedToApprove, \
    NotApprovedBy, NotInApprovableStatus
from ..models import Changeset, APPROVE_CHANGESET_PERMISSION, EDIT_CHANGESET_PERMISSION, \
    QUEUE_CHANGESET_PERMISSION


def give_approve_permission(user):
    """Give user approve permission, and return updated object"""
    user.user_permissions.add(get_permission_object_by_name(APPROVE_CHANGESET_PERMISSION))
    return refresh_model(user)


def give_queue_permission(user):
    """Give user approve permission, and return updated object"""
    perm = get_permission_object_by_name(QUEUE_CHANGESET_PERMISSION)
    user.user_permissions.add(perm)
    return refresh_model(user)


def give_edit_permission(user):
    """Give user edit permission, and return updated object"""
    perm = get_permission_object_by_name(EDIT_CHANGESET_PERMISSION)
    user.user_permissions.add(perm)
    return refresh_model(user)


class ChangesetModelTest(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_unicode(self):
        NAME = 'qesüérsdf'
        changeset = Changeset(name=NAME)
        self.assertEqual(NAME, unicode(changeset))

    def test_clean(self):
        other = ChangesetFactory(status=Changeset.STATUS_SUCCESSFUL)
        changeset = ChangesetFactory(
            change=Changeset.CHANGE_ROLLBACK,
            how_to_select=Changeset.SELECT_OTHER_CHANGESET,
            other_changeset=other,
        )
        changeset.full_clean()
        changeset.how_to_select = Changeset.SELECT_UPLOADED_NIDS
        with self.assertRaises(ValidationError):
            changeset.full_clean()
        changeset.how_to_select = Changeset.SELECT_OTHER_CHANGESET
        changeset.full_clean()
        changeset.other_changeset = None
        with self.assertRaises(ValidationError):
            changeset.full_clean()

    def test_in_editable_state(self):
        for status in [value for value, name in Changeset.STATUS_CHOICES]:
            result = Changeset(status=status).in_editable_status()
            if status < Changeset.STATUS_QUEUED:
                self.assertTrue(result)
            else:
                self.assertFalse(result)

    def test_in_queueable_state(self):
        for status in [value for value, name in Changeset.STATUS_CHOICES]:
            result = Changeset(status=status).in_queueable_status()
            if status == Changeset.STATUS_APPROVED:
                self.assertTrue(result)
            else:
                self.assertFalse(result)

    def test_may_be_edited_by(self):
        changeset = Changeset()
        self.assertFalse(changeset.may_be_edited_by(self.user))
        user = give_edit_permission(self.user)
        self.assertTrue(changeset.may_be_edited_by(user))

    def test_may_be_queued_by(self):
        changeset = Changeset()
        self.assertFalse(changeset.may_be_queued_by(self.user))
        user = give_queue_permission(self.user)
        self.assertTrue(changeset.may_be_queued_by(user))

    def test_ordering(self):
        # Changesets are ordered by creation date, descending
        stamp = now()
        changeset1 = ChangesetFactory(creation_date=stamp.replace(year=2014))
        changeset2 = ChangesetFactory(creation_date=stamp.replace(year=2013))
        changeset3 = ChangesetFactory(creation_date=stamp.replace(year=2015))
        changesets = Changeset.objects.all()
        self.assertEqual([changeset3, changeset1, changeset2], list(changesets))

    def test_approval_updates_status(self):
        changeset = ChangesetFactory(status=Changeset.STATUS_NEW)
        user = give_approve_permission(self.user)
        changeset.approve(user)
        changeset = refresh_model(changeset)
        self.assertEqual(Changeset.STATUS_NEW, changeset.status)
        user2 = give_approve_permission(UserFactory())
        changeset.approve(user2)
        changeset = refresh_model(changeset)
        self.assertEqual(Changeset.STATUS_APPROVED, changeset.status)

    def test_approval_in_wrong_state(self):
        changeset = Changeset(status=Changeset.STATUS_FAILED)
        user = give_approve_permission(self.user)
        with self.assertRaises(NotInApprovableStatus):
            changeset.approve(user)

    def test_approval_requires_permission(self):
        changeset = ChangesetFactory()
        with self.assertRaises(NotPermittedToApprove):
            changeset.approve(self.user)
        user = give_approve_permission(self.user)
        changeset.approve(user)

    def test_revoke_approval(self):
        changeset = ChangesetFactory()
        with self.assertRaises(NotApprovedBy):
            changeset.revoke_approval(self.user)
        user = give_approve_permission(self.user)
        changeset.approve(user)
        changeset.revoke_approval(user)
        self.assertEqual(0, changeset.number_of_approvals)

    def test_revoke_approval_after_queueing(self):
        changeset = ChangesetFactory()
        user = give_approve_permission(self.user)
        changeset.approve(user)
        changeset.status = Changeset.STATUS_QUEUED
        changeset.save()
        with self.assertRaises(NotInApprovableStatus):
            changeset.revoke_approval(user)

    def test_revoke_approval_updates_status(self):
        changeset = ChangesetFactory()
        user = give_approve_permission(self.user)
        user2 = give_approve_permission(UserFactory())
        changeset.approve(user)
        changeset.approve(user2)
        changeset = refresh_model(changeset)
        self.assertEqual(Changeset.STATUS_APPROVED, changeset.status)
        changeset.revoke_approval(user)
        self.assertEqual(Changeset.STATUS_NEW, changeset.status)

    def test_number_of_approvals(self):
        changeset = ChangesetFactory()
        self.assertEqual(0, changeset.number_of_approvals)
        self.user = give_approve_permission(self.user)
        changeset.approve(self.user)
        self.assertEqual(1, changeset.number_of_approvals)
        user2 = give_approve_permission(UserFactory())
        changeset.approve(user2)
        self.assertEqual(2, changeset.number_of_approvals)
        changeset.revoke_approval(user2)
        self.assertEqual(1, changeset.number_of_approvals)

    def test_in_approvable_state(self):
        self.assertTrue(Changeset(status=Changeset.STATUS_NEW).in_approvable_status())
        self.assertTrue(Changeset(status=Changeset.STATUS_APPROVED).in_approvable_status())
        self.assertFalse(Changeset(status=Changeset.STATUS_QUEUED).in_approvable_status())
        self.assertFalse(Changeset(status=Changeset.STATUS_FAILED).in_approvable_status())
        self.assertFalse(Changeset(status=Changeset.STATUS_SUCCESSFUL).in_approvable_status())
        self.assertFalse(Changeset(status=Changeset.STATUS_PARTIALLY_SUCCESSFUL)
                         .in_approvable_status())
        self.assertFalse(Changeset(status=Changeset.STATUS_ROLLED_BACK).in_approvable_status())

    def test_get_citizens_to_change_by_upload(self):
        changeset = ChangesetFactory(how_to_select=Changeset.SELECT_UPLOADED_NIDS)
        citizen1 = CitizenFactory()
        citizen2 = CitizenFactory()
        citizen3 = CitizenFactory()
        changeset.selected_citizens.add(citizen1, citizen2)
        self.assertIn(citizen1, changeset.get_citizens_to_change())
        self.assertIn(citizen2, changeset.get_citizens_to_change())
        self.assertNotIn(citizen3, changeset.get_citizens_to_change())

    def test_number_affected_after_execution(self):
        changeset = ChangesetFactory(status=Changeset.STATUS_SUCCESSFUL)
        ChangeRecordFactory(changeset=changeset, changed=True)
        ChangeRecordFactory(changeset=changeset, changed=False)
        self.assertEqual(1, changeset.number_affected())
        self.assertEqual(1, changeset.number_not_changed())

    def test_get_citizens_to_change_bad_how_to_select(self):
        changeset = ChangesetFactory(status=Changeset.STATUS_SUCCESSFUL)
        changeset.how_to_select = 99
        with self.assertRaises(NotImplementedError):
            changeset.get_citizens_to_change()
