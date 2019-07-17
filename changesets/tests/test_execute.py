"""Tests for executing changesets"""
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.http import HttpResponseForbidden
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now

from changesets.exceptions import NotAnAllowedStatus, ChangesetException
from changesets.models import QUEUE_CHANGESET_PERMISSION, Changeset
from changesets.tasks import execute_changeset
from changesets.tests.factories import ChangesetFactory, ChangeRecordFactory
from civil_registry.tests.factories import CitizenFactory
from libya_elections.utils import refresh_model
from libya_site.tests.factories import UserFactory
from register.models import Registration
from register.tests.factories import RegistrationCenterFactory, RegistrationFactory


FORBIDDEN = HttpResponseForbidden.status_code


class QueueChangesetFromViewTest(TestCase):
    def setUp(self):
        self.password = "PASSWORD"
        self.queuer = UserFactory(password=self.password)
        self.queue_changesets_group = Group.objects.get(name="Queue Changesets")
        self.queuer.groups.add(self.queue_changesets_group)
        self.login(self.queuer)

        self.changeset = ChangesetFactory(status=Changeset.STATUS_APPROVED)
        self.url = reverse('approve_changeset', kwargs={'pk': self.changeset.pk})
        self.review_url = reverse('read_changeset', kwargs={'pk': self.changeset.pk})

    def login(self, user):
        assert self.client.login(username=user.username, password=self.password)

    def test_queue_from_view(self):
        rsp = self.client.post(self.url, data={'queue': 'queue'})
        self.assertRedirects(rsp, self.review_url, msg_prefix=rsp.content.decode('utf-8'))

    def test_queue_from_view_without_permission(self):
        self.queuer.groups.remove(self.queue_changesets_group)
        assert not self.queuer.has_perm(QUEUE_CHANGESET_PERMISSION)
        assert not self.changeset.may_be_queued_by(self.queuer)
        rsp = self.client.post(self.url, data={'queue': 'queue'}, follow=False)
        self.assertEqual(FORBIDDEN, rsp.status_code)


class QueueChangesetTest(TestCase):
    def test_model_queue_method(self):
        changeset = ChangesetFactory(status=Changeset.STATUS_APPROVED)
        with patch('changesets.models.execute_changeset') as mock_task_method:
            changeset.queue()
        mock_task_method.delay.assert_called_with(changeset.pk)
        changeset = refresh_model(changeset)
        self.assertEqual(Changeset.STATUS_QUEUED, changeset.status)

    def test_model_queue_bad_status(self):
        changeset = ChangesetFactory(status=Changeset.STATUS_NEW)
        with patch('changesets.models.execute_changeset') as mock_task_method:
            with self.assertRaises(NotAnAllowedStatus):
                changeset.queue()
        mock_task_method.delay.assert_not_called()
        changeset = refresh_model(changeset)
        self.assertEqual(Changeset.STATUS_NEW, changeset.status)

    def test_task_calls_model_execute(self):
        changeset = ChangesetFactory(status=Changeset.STATUS_APPROVED)
        with patch('changesets.models.Changeset.execute') as mock_execute:
            execute_changeset(changeset.pk)
        assert mock_execute.called

    def test_queue_method_bad_status(self):
        changeset = ChangesetFactory(status=Changeset.STATUS_NEW)
        with self.assertRaises(NotAnAllowedStatus):
            changeset.queue()


class ExecuteChangesetTest(TestCase):
    def test_execute_bad_status(self):
        changeset = ChangesetFactory(status=Changeset.STATUS_NEW)
        with self.assertRaises(NotAnAllowedStatus):
            changeset.execute()

    def test_execute_bad_change_type(self):
        changeset = ChangesetFactory(status=Changeset.STATUS_APPROVED)
        changeset.full_clean()
        changeset.change = 99
        with self.assertRaises(ChangesetException):
            changeset.execute()

    def test_rollback_bad_status(self):
        changeset = ChangesetFactory(
            status=Changeset.STATUS_APPROVED,
            change=Changeset.CHANGE_ROLLBACK,
            other_changeset=ChangesetFactory(status=Changeset.STATUS_FAILED),
        )
        with self.assertRaises(NotAnAllowedStatus):
            changeset.execute()

    def test_exception_fails_execute(self):
        changeset = ChangesetFactory(
            status=Changeset.STATUS_APPROVED,
            change=Changeset.CHANGE_CENTER,
            how_to_select=Changeset.SELECT_UPLOADED_NIDS,
        )
        with patch.object(Changeset, 'get_registrations_to_change') as get_reg:
            get_reg.side_effect = TypeError
            changeset.execute()
        changeset = refresh_model(changeset)
        self.assertEqual(Changeset.STATUS_FAILED, changeset.status)


class ExecuteBlockTest(TestCase):
    """
    Test executing blocking changesets.

    Each test will set up a change in a different way but that ought to have the same
    results. Then we'll try to roll back the change, after changing one voter, and check
    those results.
    """
    def setUp(self):
        # these should be blocked during the changeset
        self.citizen1 = CitizenFactory()
        self.citizen2 = CitizenFactory()
        # citizen3 already blocked
        self.citizen3 = CitizenFactory()
        self.citizen3.block()
        # citizen4 won't be included
        self.citizen4 = CitizenFactory()

        self.changeset = ChangesetFactory(
            status=Changeset.STATUS_APPROVED,
            change=Changeset.CHANGE_BLOCK,
        )

    def doit(self):
        self.changeset.full_clean()
        citizens = list(self.changeset.get_citizens_to_change())
        self.assertIn(self.citizen1, citizens)
        self.assertIn(self.citizen2, citizens)
        self.assertIn(self.citizen3, citizens)  # In the list, but will not be changed
        self.assertNotIn(self.citizen4, citizens)

        self.changeset.execute()
        self.citizen1 = refresh_model(self.citizen1)
        self.citizen2 = refresh_model(self.citizen2)
        self.citizen3 = refresh_model(self.citizen3)
        self.citizen4 = refresh_model(self.citizen4)
        self.assertTrue(self.citizen1.blocked)
        self.assertTrue(self.citizen2.blocked)
        self.assertTrue(self.citizen3.blocked)
        self.assertFalse(self.citizen4.blocked)

        changes = self.changeset.change_records.all()
        self.assertTrue(changes.filter(citizen=self.citizen1, changed=True).exists())
        self.assertTrue(changes.filter(citizen=self.citizen2, changed=True).exists())
        self.assertTrue(changes.filter(citizen=self.citizen3, changed=False).exists())
        self.assertFalse(changes.filter(citizen=self.citizen4).exists())

        self.assertEqual(Changeset.STATUS_PARTIALLY_SUCCESSFUL, self.changeset.status)

        # Now unblock citizen 2
        self.citizen2.unblock()

        rollback = ChangesetFactory(
            status=Changeset.STATUS_APPROVED,
            change=Changeset.CHANGE_ROLLBACK,
            how_to_select=Changeset.SELECT_OTHER_CHANGESET,
            other_changeset=self.changeset,
        )
        citizens = list(rollback.get_citizens_to_change())
        self.assertIn(self.citizen1, citizens)
        self.assertIn(self.citizen2, citizens)
        self.assertNotIn(self.citizen3, citizens)  # not changed before, so not in list this time
        self.assertNotIn(self.citizen4, citizens)

        rollback.execute()
        self.changeset = refresh_model(self.changeset)
        self.assertEqual(Changeset.STATUS_ROLLED_BACK, self.changeset.status)

        self.citizen1 = refresh_model(self.citizen1)
        self.citizen2 = refresh_model(self.citizen2)
        self.citizen3 = refresh_model(self.citizen3)
        self.citizen4 = refresh_model(self.citizen4)
        self.assertFalse(self.citizen1.blocked)
        self.assertFalse(self.citizen2.blocked)
        self.assertTrue(self.citizen3.blocked)
        self.assertFalse(self.citizen4.blocked)

        changes = rollback.change_records.all()
        self.assertTrue(changes.filter(citizen=self.citizen1, changed=True).exists())
        self.assertTrue(changes.filter(citizen=self.citizen2, changed=False).exists())
        # reg 3 not in the list because they were changed previously
        self.assertFalse(changes.filter(citizen=self.citizen3).exists())
        self.assertFalse(changes.filter(citizen=self.citizen4).exists())
        self.assertEqual(Changeset.STATUS_PARTIALLY_SUCCESSFUL, rollback.status)

    def test_block_by_uploaded_citizens(self):
        self.changeset.how_to_select = Changeset.SELECT_UPLOADED_NIDS
        self.changeset.save()
        self.changeset.selected_citizens.add(self.citizen1, self.citizen2, self.citizen3)
        self.doit()

    def test_block_by_selected_centers(self):
        center1 = RegistrationCenterFactory()
        center2 = RegistrationCenterFactory()
        RegistrationCenterFactory()
        RegistrationFactory(citizen=self.citizen1, registration_center=center1,
                            archive_time=None)
        RegistrationFactory(citizen=self.citizen2, registration_center=center1,
                            archive_time=None)
        RegistrationFactory(citizen=self.citizen3, registration_center=center2,
                            archive_time=None)
        self.changeset.how_to_select = Changeset.SELECT_CENTERS
        self.changeset.save()
        self.changeset.selected_centers.add(center1, center2)
        self.doit()

    def test_block_by_other_changeset(self):
        other = ChangesetFactory(status=Changeset.STATUS_SUCCESSFUL)
        self.changeset.how_to_select = Changeset.SELECT_OTHER_CHANGESET
        self.changeset.other_changeset = other
        self.changeset.save()
        ChangeRecordFactory(citizen=self.citizen1, changeset=other, changed=True)
        ChangeRecordFactory(citizen=self.citizen2, changeset=other, changed=True)
        ChangeRecordFactory(citizen=self.citizen3, changeset=other, changed=True)
        ChangeRecordFactory(citizen=self.citizen4, changeset=other, changed=False)
        self.doit()


class ExecuteUnblockTest(TestCase):
    """
    Test executing unblocking changesets.

    Each test will set up a change in a different way but that ought to have the same
    results. Then we'll try to roll back the change, after changing one voter, and check
    those results.
    """
    def setUp(self):
        # these should be unblocked during the changeset
        self.citizen1 = CitizenFactory()
        self.citizen1.block()
        self.citizen2 = CitizenFactory()
        self.citizen2.block()
        # citizen3 already unblocked
        self.citizen3 = CitizenFactory()
        # citizen4 won't be included
        self.citizen4 = CitizenFactory()
        self.citizen4.block()

        self.changeset = ChangesetFactory(
            status=Changeset.STATUS_APPROVED,
            change=Changeset.CHANGE_UNBLOCK,
        )

    def doit(self):
        self.changeset.full_clean()
        citizens = list(self.changeset.get_citizens_to_change())
        self.assertIn(self.citizen1, citizens)
        self.assertIn(self.citizen2, citizens)
        self.assertIn(self.citizen3, citizens)  # In the list, but will not be changed
        self.assertNotIn(self.citizen4, citizens)

        self.changeset.execute()
        self.citizen1 = refresh_model(self.citizen1)
        self.citizen2 = refresh_model(self.citizen2)
        self.citizen3 = refresh_model(self.citizen3)
        self.citizen4 = refresh_model(self.citizen4)
        self.assertFalse(self.citizen1.blocked)
        self.assertFalse(self.citizen2.blocked)
        self.assertFalse(self.citizen3.blocked)
        self.assertTrue(self.citizen4.blocked)

        changes = self.changeset.change_records.all()
        self.assertTrue(changes.filter(citizen=self.citizen1, changed=True).exists())
        self.assertTrue(changes.filter(citizen=self.citizen2, changed=True).exists())
        self.assertTrue(changes.filter(citizen=self.citizen3, changed=False).exists())
        self.assertFalse(changes.filter(citizen=self.citizen4).exists())

        self.assertEqual(Changeset.STATUS_PARTIALLY_SUCCESSFUL, self.changeset.status)

        # Now block citizen 2
        self.citizen2.block()

        rollback = ChangesetFactory(
            status=Changeset.STATUS_APPROVED,
            change=Changeset.CHANGE_ROLLBACK,
            how_to_select=Changeset.SELECT_OTHER_CHANGESET,
            other_changeset=self.changeset,
        )
        citizens = list(rollback.get_citizens_to_change())
        self.assertIn(self.citizen1, citizens)
        self.assertIn(self.citizen2, citizens)
        self.assertNotIn(self.citizen3, citizens)  # not changed before, so not in list this time
        self.assertNotIn(self.citizen4, citizens)

        rollback.execute()
        self.changeset = refresh_model(self.changeset)
        self.assertEqual(Changeset.STATUS_ROLLED_BACK, self.changeset.status)

        self.citizen1 = refresh_model(self.citizen1)
        self.citizen2 = refresh_model(self.citizen2)
        self.citizen3 = refresh_model(self.citizen3)
        self.citizen4 = refresh_model(self.citizen4)
        self.assertTrue(self.citizen1.blocked)
        self.assertTrue(self.citizen2.blocked)
        self.assertFalse(self.citizen3.blocked)
        self.assertTrue(self.citizen4.blocked)

        changes = rollback.change_records.all()
        self.assertTrue(changes.filter(citizen=self.citizen1, changed=True).exists())
        self.assertTrue(changes.filter(citizen=self.citizen2, changed=False).exists())
        # reg 3 not in the list because they were changed previously
        self.assertFalse(changes.filter(citizen=self.citizen3).exists())
        self.assertFalse(changes.filter(citizen=self.citizen4).exists())
        self.assertEqual(Changeset.STATUS_PARTIALLY_SUCCESSFUL, rollback.status)

    def test_unblock_by_uploaded_citizens(self):
        self.changeset.how_to_select = Changeset.SELECT_UPLOADED_NIDS
        self.changeset.save()
        self.changeset.selected_citizens.add(self.citizen1, self.citizen2, self.citizen3)
        self.doit()

    def test_unblock_by_selected_centers(self):
        center1 = RegistrationCenterFactory()
        center2 = RegistrationCenterFactory()
        RegistrationCenterFactory()
        RegistrationFactory(citizen=self.citizen1, registration_center=center1,
                            archive_time=None)
        RegistrationFactory(citizen=self.citizen2, registration_center=center1,
                            archive_time=None)
        RegistrationFactory(citizen=self.citizen3, registration_center=center2,
                            archive_time=None)
        self.changeset.how_to_select = Changeset.SELECT_CENTERS
        self.changeset.save()
        self.changeset.selected_centers.add(center1, center2)
        self.doit()

    def test_unblock_by_other_changeset(self):
        other = ChangesetFactory(status=Changeset.STATUS_SUCCESSFUL)
        self.changeset.how_to_select = Changeset.SELECT_OTHER_CHANGESET
        self.changeset.other_changeset = other
        self.changeset.save()
        ChangeRecordFactory(citizen=self.citizen1, changeset=other, changed=True)
        ChangeRecordFactory(citizen=self.citizen2, changeset=other, changed=True)
        ChangeRecordFactory(citizen=self.citizen3, changeset=other, changed=True)
        ChangeRecordFactory(citizen=self.citizen4, changeset=other, changed=False)
        self.doit()


class MissingCitizenCenterChangeTest(TestCase):
    def test_missing_citizen_center_change(self):
        self.from_center = RegistrationCenterFactory()
        self.to_center = RegistrationCenterFactory()
        self.reg = RegistrationFactory(registration_center=self.from_center, archive_time=None)

        self.changeset = ChangesetFactory(
            status=Changeset.STATUS_APPROVED,
            change=Changeset.CHANGE_CENTER,
            how_to_select=Changeset.SELECT_CENTERS,
            target_center=self.to_center
        )
        self.changeset.selected_centers.add(self.from_center)

        # Mark the citizen as missing (which will exclude it from Citizen queries per the default
        # manager)
        self.reg.citizen.missing = now()
        self.reg.citizen.save()

        # Make sure the registration is still around, otherwise something in the test
        # broke and it's no longer valid.
        Registration.objects.get(pk=self.reg.pk)

        self.changeset.execute()
        self.changeset.refresh_from_db()
        self.assertEqual(self.changeset.status, Changeset.STATUS_SUCCESSFUL)


class ExecuteCenterChangeTest(TestCase):
    """
    Test executeing center change changesets.

    Each test will set up a change in a different way but that ought to have the same
    results. Then we'll try to roll back the change, after having one voter change
    their registration, and check those results.
    """
    def setUp(self):
        self.from_center_1 = RegistrationCenterFactory()
        self.from_center_2 = RegistrationCenterFactory()
        self.center_3 = RegistrationCenterFactory()
        self.to_center = RegistrationCenterFactory()
        # these should be moved
        self.reg1 = RegistrationFactory(registration_center=self.from_center_1, archive_time=None)
        self.reg2 = RegistrationFactory(registration_center=self.from_center_2, archive_time=None)
        # these should not
        self.reg3 = RegistrationFactory(registration_center=self.center_3, archive_time=None)
        self.reg4 = RegistrationFactory(registration_center=self.to_center, archive_time=None)

        self.changeset = ChangesetFactory(
            status=Changeset.STATUS_APPROVED,
            change=Changeset.CHANGE_CENTER,
            target_center=self.to_center
        )

    def doit(self):
        # Execute the changeset and check out the results
        self.changeset.full_clean()
        citizens = self.changeset.get_citizens_to_change()
        self.assertIn(self.reg1.citizen, citizens)
        self.assertIn(self.reg2.citizen, citizens)
        self.assertNotIn(self.reg3.citizen, citizens)
        # citizen4 might or might not be in the 'get_citizens_to_change' result depending
        # on the test

        self.changeset.execute()
        self.assertEqual(self.to_center, refresh_model(self.reg1).registration_center)
        # There should also be an archived registration that is unchanged
        archives = Registration.objects.archived()
        self.assertEqual(1, archives.filter(citizen=self.reg1.citizen,
                                            registration_center=self.from_center_1).count())
        self.assertEqual(self.to_center, refresh_model(self.reg2).registration_center)
        # There should also be an archived registration that is unchanged
        self.assertEqual(1, archives.filter(citizen=self.reg2.citizen,
                                            registration_center=self.from_center_2).count())
        # reg 3 not moved, was at center 3
        self.assertEqual(self.center_3, refresh_model(self.reg3).registration_center)
        # No archived center
        self.assertFalse(archives.filter(citizen=self.reg3.citizen).exists())
        # reg 4 not moved, but was already at to_center
        self.assertEqual(self.to_center, refresh_model(self.reg4).registration_center)
        # No archived center
        self.assertFalse(archives.filter(citizen=self.reg4.citizen).exists())
        changeset = refresh_model(self.changeset)
        if self.changeset.how_to_select == Changeset.SELECT_UPLOADED_NIDS:
            # Ugh - this was the only test where we could "add" citizen4
            self.assertEqual(Changeset.STATUS_PARTIALLY_SUCCESSFUL, changeset.status)
        else:
            self.assertEqual(Changeset.STATUS_SUCCESSFUL, changeset.status)
        changes = changeset.change_records
        self.assertEqual(1, changes.filter(citizen=self.reg1.citizen, changed=True).count())
        self.assertEqual(1, changes.filter(citizen=self.reg2.citizen, changed=True).count())
        # self.reg3 shouldn't be mentioned, they weren't in the set to be changed
        self.assertFalse(changes.filter(citizen=self.reg3.citizen).exists())
        # self.reg4 might or might not have a change record, but if it does, changed
        # should be False
        self.assertFalse(changes.filter(citizen=self.reg4.citizen, changed=True).exists())

        # the citizen from self.reg2 moves themselves to another center, so they
        # should not be rolled back
        self.reg2.registration_center = self.center_3
        self.reg2.save()

        # Do a rollback
        rollback = ChangesetFactory(
            status=Changeset.STATUS_APPROVED,
            change=Changeset.CHANGE_ROLLBACK,
            how_to_select=Changeset.SELECT_OTHER_CHANGESET,
            other_changeset=changeset,
        )
        rollback.full_clean()
        citizens = list(rollback.get_citizens_to_change())
        self.assertIn(self.reg1.citizen, citizens)
        self.assertIn(self.reg2.citizen, citizens)  # In the list, but we won't change them
        self.assertNotIn(self.reg3.citizen, citizens)
        self.assertNotIn(self.reg4.citizen, citizens)  # was not changed
        rollback.execute()
        rollback = refresh_model(rollback)
        self.assertEqual(Changeset.STATUS_PARTIALLY_SUCCESSFUL, rollback.status)
        changeset = refresh_model(changeset)
        self.assertEqual(Changeset.STATUS_ROLLED_BACK, changeset.status)
        self.assertEqual(rollback, changeset.rollback_changeset)
        self.assertEqual(self.from_center_1, refresh_model(self.reg1).registration_center)
        # reg1 was changed then changed back, so there should be two archived versions
        self.assertEqual(2, archives.filter(citizen=self.reg1.citizen).count())
        self.assertEqual(1, archives.filter(citizen=self.reg1.citizen,
                                            registration_center=self.from_center_1).count())
        self.assertEqual(1, archives.filter(citizen=self.reg1.citizen,
                                            registration_center=self.to_center).count())
        self.assertEqual(self.center_3, refresh_model(self.reg2).registration_center)
        self.assertEqual(1, rollback.change_records.filter(citizen=self.reg1.citizen, changed=True)
                         .count())
        self.assertEqual(1, rollback.change_records.filter(citizen=self.reg2.citizen, changed=False)
                         .count())

    def test_execute_center_change_by_center_and_partial_rollback(self):
        # test selecting voters by center
        self.changeset.how_to_select = Changeset.SELECT_CENTERS
        self.changeset.save()
        self.changeset.selected_centers.add(self.from_center_1, self.from_center_2)
        self.doit()

    def test_execute_center_change_by_upload_and_partial_rollback(self):
        # test selecting voters by upload
        self.changeset.how_to_select = Changeset.SELECT_UPLOADED_NIDS
        self.changeset.save()
        self.changeset.selected_citizens.add(self.reg1.citizen, self.reg2.citizen,
                                             self.reg4.citizen)
        self.doit()

    def test_execute_center_change_by_another_changeset_and_partial_rollback(self):
        # test selecting voters from another changeset
        first_changeset = ChangesetFactory(status=Changeset.STATUS_SUCCESSFUL)
        ChangeRecordFactory(changeset=first_changeset, citizen=self.reg1.citizen, changed=True)
        ChangeRecordFactory(changeset=first_changeset, citizen=self.reg2.citizen, changed=True)
        # reg3 had a change record, but was not changed
        ChangeRecordFactory(changeset=first_changeset, citizen=self.reg3.citizen, changed=False)
        # reg4 doesn't show up at all

        self.changeset.how_to_select = Changeset.SELECT_OTHER_CHANGESET
        self.changeset.other_changeset = first_changeset
        self.changeset.save()
        self.doit()
