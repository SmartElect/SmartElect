from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpRequest
from django.test import TestCase

from mock import patch, MagicMock

from civil_registry.models import Citizen
from civil_registry.tests.factories import CitizenFactory
from libya_elections.utils import refresh_model, get_permission_object_by_name
from libya_site.tests.factories import UserFactory
from register.tests.factories import RegistrationCenterFactory

from ..forms import ChangesetForm
from ..models import Changeset, APPROVE_CHANGESET_PERMISSION
from ..tests.factories import ChangesetFactory


class ChangesetFormTest(TestCase):
    def setUp(self):
        self.center1 = RegistrationCenterFactory()
        self.center2 = RegistrationCenterFactory()
        self.center3 = RegistrationCenterFactory()
        self.data = {
            'name': 'My Changeset',
            'change': str(Changeset.CHANGE_CENTER),
            'how_to_select': str(Changeset.SELECT_CENTERS),
            # django-selectable appends "_1" to the field name for the form name that
            # has the actual data submitted:
            'selected_centers_1': [str(self.center1.pk), str(self.center2.pk)],
            'target_center_1': str(self.center3.pk),
            'justification': 'Just because',
        }

    def test_create_changeset(self):
        # We can create a changeset
        mock_request = MagicMock(user=UserFactory())
        form = ChangesetForm(data=self.data, request=mock_request)
        self.assertTrue(form.is_valid(), msg=str(form.errors))
        changeset = form.save()
        changeset = refresh_model(changeset)
        self.assertEqual(Changeset.CHANGE_CENTER, changeset.change)
        self.assertEqual(Changeset.SELECT_CENTERS, changeset.how_to_select)
        self.assertIn(self.center1, changeset.selected_centers.all())
        self.assertIn(self.center2, changeset.selected_centers.all())

    def test_cannot_move_to_same_center(self):
        # We prevent moving from a center to the same center
        self.data['target_center_1'] = str(self.center1.pk)
        form = ChangesetForm(data=self.data, request=MagicMock())
        self.assertFalse(form.is_valid())
        self.assertIn('target_center', form.errors)

    def test_select_center_must_specify_selected_centers(self):
        # If how_to_select is SELECT_CENTERS, you have to specify some
        del self.data['selected_centers_1']
        form = ChangesetForm(data=self.data, request=MagicMock())
        self.assertFalse(form.is_valid())
        self.assertIn('selected_centers', form.errors)

    def test_change_center_must_specify_target_center(self):
        # If changing centers, must give a target
        del self.data['target_center_1']
        form = ChangesetForm(data=self.data, request=MagicMock())
        self.assertFalse(form.is_valid())
        self.assertIn('target_center', form.errors)

    def test_select_other_changeset_requires_other_changeset(self):
        # If how_to_select is SELECT_OTHER_CHANGESET, you have to give another changeset
        data = self.data
        data['how_to_select'] = str(Changeset.SELECT_OTHER_CHANGESET)
        form = ChangesetForm(data=self.data, request=MagicMock())
        self.assertFalse(form.is_valid())
        self.assertIn('other_changeset', form.errors)

    def test_rollback_requires_other_changeset(self):
        # Rollback always requires another changeset
        data = self.data
        data['change'] = str(Changeset.CHANGE_ROLLBACK)
        form = ChangesetForm(data=self.data, request=MagicMock())
        self.assertFalse(form.is_valid())
        self.assertIn('other_changeset', form.errors)

    def test_rollback_other_changeset_must_not_have_failed(self):
        # You can't rollback a failed changeset
        data = self.data
        data['change'] = str(Changeset.CHANGE_ROLLBACK)
        changeset2 = ChangesetFactory(status=Changeset.STATUS_FAILED)
        data['other_changeset'] = str(changeset2.pk)
        form = ChangesetForm(data=self.data, request=MagicMock())
        self.assertFalse(form.is_valid())
        self.assertIn('other_changeset', form.errors)

    def test_rollback_other_changeset_can_be_partially_successful(self):
        # You can rollback a partially successful changeset
        data = self.data
        data['change'] = str(Changeset.CHANGE_ROLLBACK)
        changeset2 = ChangesetFactory(status=Changeset.STATUS_PARTIALLY_SUCCESSFUL)
        data['other_changeset'] = str(changeset2.pk)
        data['how_to_select'] = str(Changeset.SELECT_OTHER_CHANGESET)
        form = ChangesetForm(data=self.data, request=MagicMock())
        self.assertTrue(form.is_valid(), msg=form.errors)

    def test_select_uploaded_nids_requires_uploaded_file(self):
        # If how_to_select is upload NIDs, you must upload a file
        data = self.data
        data['how_to_select'] = str(Changeset.SELECT_UPLOADED_NIDS)
        form = ChangesetForm(data=data, files={}, request=MagicMock())
        self.assertFalse(form.is_valid())
        self.assertIn('upload_file', form.errors)

    def test_max_upload_errors(self):
        # We stop reporting upload errors beyond MAX_ERRORS
        data = self.data
        data['how_to_select'] = str(Changeset.SELECT_UPLOADED_NIDS)
        filetext = "1\n2\n3\n4\n"
        upload_file = SimpleUploadedFile('my_filename', filetext)
        form = ChangesetForm(data=data, files={'upload_file': upload_file}, request=MagicMock())
        with patch('changesets.forms.MAX_ERRORS', 1):
            self.assertFalse(form.is_valid())
        self.assertIn('upload_file', form.errors)
        self.assertIn('Stopping', str(form.errors))

    def test_upload_file(self):
        # We can successfully upload a file of NIDs and look up the citizens
        # and blank lines are okay
        data = self.data
        data['how_to_select'] = str(Changeset.SELECT_UPLOADED_NIDS)
        citizen1 = CitizenFactory()
        citizen2 = CitizenFactory()
        filetext = "{nid1}\n\n{nid2}\n".format(nid1=citizen1.national_id, nid2=citizen2.national_id)
        upload_file = SimpleUploadedFile('my_filename', filetext)
        mock_request = MagicMock(user=UserFactory())
        form = ChangesetForm(data=data, files={'upload_file': upload_file}, request=mock_request)
        self.assertTrue(form.is_valid(), msg=str(form.errors))
        changeset = form.save()
        self.assertIn(citizen1, changeset.selected_citizens.all())
        self.assertIn(citizen2, changeset.selected_citizens.all())

    def test_upload_file_not_number(self):
        # We catch non-numbers in the upload file
        data = self.data
        data['how_to_select'] = str(Changeset.SELECT_UPLOADED_NIDS)
        citizen1 = CitizenFactory()
        citizen2 = CitizenFactory()
        nid1 = str(citizen1.national_id)
        nid1 = nid1[0] + '.' + nid1[2:]
        filetext = "{nid1}\n{nid2}\n".format(nid1=nid1, nid2=citizen2.national_id)
        upload_file = SimpleUploadedFile('my_filename', filetext)
        form = ChangesetForm(data=data, files={'upload_file': upload_file}, request=MagicMock())
        self.assertFalse(form.is_valid())
        self.assertIn('upload_file', form.errors)

    def test_upload_file_invalid_nid(self):
        # We catch invalid NIDs in the upload file
        data = self.data
        data['how_to_select'] = str(Changeset.SELECT_UPLOADED_NIDS)
        citizen1 = CitizenFactory()
        citizen2 = CitizenFactory()
        nid1 = str(citizen1.national_id)
        nid1 = '3' + nid1[1:]
        filetext = "{nid1}\n{nid2}\n".format(nid1=nid1, nid2=citizen2.national_id)
        upload_file = SimpleUploadedFile('my_filename', filetext)
        form = ChangesetForm(data=data, files={'upload_file': upload_file}, request=MagicMock())
        self.assertFalse(form.is_valid())
        self.assertIn('upload_file', form.errors)

    def test_upload_file_no_such_citizen(self):
        # We catch non-existent citizens in the upload file
        data = self.data
        data['how_to_select'] = str(Changeset.SELECT_UPLOADED_NIDS)
        citizen1 = CitizenFactory()
        citizen2 = CitizenFactory()
        filetext = "{nid1}\n{nid2}\n".format(nid1=citizen1.national_id + 27,
                                             nid2=citizen2.national_id)
        upload_file = SimpleUploadedFile('my_filename', filetext)
        with patch('changesets.forms.get_citizen_by_national_id') as mock_get_citizen:
            mock_get_citizen.return_value = None  # No such citizen
            form = ChangesetForm(data=data, files={'upload_file': upload_file}, request=MagicMock())
            self.assertFalse(form.is_valid())
            self.assertIn('upload_file', form.errors)

    def test_upload_file_might_have_to_lookup_citizen(self):
        # Upload file can have a citizen we don't have a Citizen record for yet
        # (e.g. if we're blocking a citizen who hasn't tried to register)
        data = self.data
        data['how_to_select'] = str(Changeset.SELECT_UPLOADED_NIDS)
        nid1 = "199999999999"
        filetext = "{nid1}\n".format(nid1=nid1)
        upload_file = SimpleUploadedFile('my_filename', filetext)
        with patch('changesets.forms.get_citizen_by_national_id') as mock_get_citizen:
            # Make a Citizen but don't save it in the database, so the form validation
            # won't initially find it
            citizen = Citizen(national_id=nid1)
            mock_get_citizen.return_value = citizen
            form = ChangesetForm(data=data, files={'upload_file': upload_file}, request=MagicMock())
            self.assertTrue(form.is_valid())

    def test_upload_file_invalid_line(self):
        # We notice a file with too short a line
        data = self.data
        data['how_to_select'] = str(Changeset.SELECT_UPLOADED_NIDS)
        citizen1 = CitizenFactory()
        citizen2 = CitizenFactory()
        filetext = "1{nid1}\n{nid2}\n".format(nid1=citizen1.national_id, nid2=citizen2.national_id)
        upload_file = SimpleUploadedFile('my_filename', filetext)
        form = ChangesetForm(data=data, files={'upload_file': upload_file}, request=MagicMock())
        self.assertFalse(form.is_valid())
        self.assertIn('upload_file', form.errors)

    def test_upload_file_empty(self):
        # We don't allow an empty file
        data = self.data
        data['how_to_select'] = str(Changeset.SELECT_UPLOADED_NIDS)
        filetext = ""
        upload_file = SimpleUploadedFile('my_filename', filetext)
        form = ChangesetForm(data=data, files={'upload_file': upload_file}, request=MagicMock())
        self.assertFalse(form.is_valid())
        self.assertIn('upload_file', form.errors)
        self.assertIn("The submitted file is empty.", str(form.errors))

    def test_approval_warning_checkbox(self):
        # If the changeset has approvals, we include the approval warning checkbox
        # If not, we don't.

        # New changeset
        form = ChangesetForm(data=self.data, request=MagicMock())
        self.assertNotIn('okay_to_remove_approvals', form.fields)

        # Existing changeset without approvals
        changeset = ChangesetFactory()
        form = ChangesetForm(instance=changeset, data=self.data, request=MagicMock())
        self.assertNotIn('okay_to_remove_approvals', form.fields)

        # Approvals
        self.approver = UserFactory()
        self.approver.user_permissions.add(
            get_permission_object_by_name(APPROVE_CHANGESET_PERMISSION))
        changeset.approve(self.approver)
        form = ChangesetForm(instance=changeset, data=self.data, request=MagicMock())
        self.assertIn('okay_to_remove_approvals', form.fields)

        # And we must check it
        self.assertFalse(form.is_valid())
        self.assertIn('okay_to_remove_approvals', form.errors)

        # If we save, it removes the approvals
        self.data['okay_to_remove_approvals'] = True
        mock_request = MagicMock()
        mock_request.__class__ = HttpRequest
        form = ChangesetForm(instance=changeset, data=self.data, request=mock_request)
        self.assertTrue(form.is_valid(), form.errors)
        changeset = form.save()
        self.assertEqual(0, changeset.number_of_approvals)
