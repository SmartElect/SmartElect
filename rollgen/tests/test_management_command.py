# Python imports
from __future__ import unicode_literals
from __future__ import division
import logging
import os
import shutil
import tempfile

# 3rd party imports
from mock import patch, ANY

# Django imports
from django.core.management.base import CommandError
from django.core.management import call_command
from django.test import TestCase

# Project imports
from ..job import PHASES
from libya_elections.constants import CENTER_ID_MAX_INT_VALUE, NO_NAMEDTHING
from register.models import Office
from register.tests.factories import RegistrationCenterFactory, RegistrationFactory
from voting.models import Election

# Silence the logging output.
logging.disable(logging.CRITICAL)


@patch('rollgen.job.Job.__init__')
@patch('rollgen.job.Job.generate_rolls')
class TestManagementCommand(TestCase):
    """Exercise the generate_rolls mgmt command, especially options"""
    def setUp(self):
        self.centers = [RegistrationCenterFactory(), RegistrationCenterFactory()]
        # Add a center not supporting registrations with the same office and constituency
        # as a center that does support registrations.  It should be ignored.
        self.inactive_center = RegistrationCenterFactory(reg_open=False,
                                                         office=self.centers[0].office,
                                                         constituency=self.centers[0].constituency)
        # Ensure the classes are sorted in the same order as the database uses
        self.centers.sort(key=lambda center: center.center_id)
        self.username = os.environ.get('USER', 'unknown')
        self.command_name = 'generate_rolls'
        self.temp_dir = tempfile.mkdtemp()

        self.phase = 'in-person'

        self.input_arguments = {'phase': self.phase,
                                'forgive_no_voters': False,
                                'forgive_no_office': False,
                                'office_ids': [],
                                'center_ids': [],
                                'constituency_ids': [],
                                }

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def get_temp_file(self):
        """Return a file object for a temp file that will be automatically cleaned up"""
        f, filename = tempfile.mkstemp(dir=self.temp_dir)
        os.close(f)
        return open(filename, 'w')

    def test_phase_required(self, mock_generate_rolls, mock_ctor):
        """Ensure that one must specify the phase"""
        with self.assertRaises(CommandError) as cm:
            call_command(self.command_name)
        msg = 'Please specify exactly one of the following phases: ' + ', '.join(PHASES.keys())
        self.assertEqual(cm.exception.message, msg)

    def test_nonsense_phase_rejected(self, mock_generate_rolls, mock_ctor):
        """Ensure that only valid phases are accepted"""
        with self.assertRaises(CommandError) as cm:
            call_command(self.command_name, 'banana')
        expected_message = 'Phase must be one of {}'.format(', '.join(PHASES.keys()))
        self.assertEqual(cm.exception.message, expected_message)

    def test_phases(self, mock_generate_rolls, mock_ctor):
        """Exercise simple invocations and ensure expected calls are made"""
        mock_ctor.return_value = None

        for phase in PHASES.keys():
            self.input_arguments['phase'] = phase

            call_command(self.command_name, phase)

            mock_ctor.assert_called_once_with(phase, self.centers, self.input_arguments,
                                              self.username, ANY)
            self.assertTrue(mock_generate_rolls.called)

            mock_ctor.reset_mock()
            mock_generate_rolls.reset_mock()

    def test_center_id_file_option(self, mock_generate_rolls, mock_ctor):
        """Exercise center-id-file option"""
        mock_ctor.return_value = None

        f = self.get_temp_file()
        f.write(str(self.centers[0].center_id))
        f.close()

        self.input_arguments['center_ids'] = [self.centers[0].center_id]

        call_command(self.command_name, self.phase, center_id_file=f.name)

        mock_ctor.assert_called_once_with(self.phase, [self.centers[0]], self.input_arguments,
                                          self.username, ANY)

        self.assertTrue(mock_generate_rolls.called)

    def test_center_id_list_option(self, mock_generate_rolls, mock_ctor):
        """Exercise center-id-list option"""
        mock_ctor.return_value = None

        self.input_arguments['center_ids'] = [self.centers[0].center_id]

        call_command(self.command_name, self.phase, center_ids=str(self.centers[0].center_id))

        mock_ctor.assert_called_once_with(self.phase, [self.centers[0]], self.input_arguments,
                                          self.username, ANY)
        self.assertTrue(mock_generate_rolls.called)

    def test_center_id_list_option_inactive_center(self, mock_generate_rolls, mock_ctor):
        """Ensure the center-id-list option rejects an inactive center"""
        mock_ctor.return_value = None

        self.input_arguments['center_ids'] = [self.inactive_center.center_id]

        with self.assertRaises(CommandError) as cm:
            call_command(self.command_name, self.phase,
                         center_ids=str(self.inactive_center.center_id))

        self.assertEqual(cm.exception.message, "The criteria you provided match no active centers.")

        self.assertFalse(mock_ctor.called)
        self.assertFalse(mock_generate_rolls.called)

    def test_office_id_file_option(self, mock_generate_rolls, mock_ctor):
        """Exercise office-id-file option"""
        mock_ctor.return_value = None

        f = self.get_temp_file()
        f.write(str(self.centers[0].office.id))
        f.close()

        self.input_arguments['office_ids'] = [self.centers[0].office.id]

        call_command(self.command_name, self.phase, office_id_file=f.name)

        mock_ctor.assert_called_once_with(self.phase, [self.centers[0]], self.input_arguments,
                                          self.username, ANY)
        self.assertTrue(mock_generate_rolls.called)

    def test_office_id_list_option(self, mock_generate_rolls, mock_ctor):
        """Exercise office-id-list option"""
        mock_ctor.return_value = None

        self.input_arguments['office_ids'] = [self.centers[0].office.id]

        call_command(self.command_name, self.phase, office_ids=str(self.centers[0].office.id))

        mock_ctor.assert_called_once_with(self.phase, [self.centers[0]], self.input_arguments,
                                          self.username, ANY)
        self.assertTrue(mock_generate_rolls.called)

    def test_constituency_id_file_option(self, mock_generate_rolls, mock_ctor):
        """Exercise constituency-id-file option"""
        mock_ctor.return_value = None

        f = self.get_temp_file()
        f.write(str(self.centers[0].constituency.id))
        f.close()

        self.input_arguments['constituency_ids'] = [self.centers[0].constituency.id]

        call_command(self.command_name, self.phase, constituency_id_file=f.name)

        mock_ctor.assert_called_once_with(self.phase, [self.centers[0]], self.input_arguments,
                                          self.username, ANY)
        self.assertTrue(mock_generate_rolls.called)

    def test_constituency_id_list_option(self, mock_generate_rolls, mock_ctor):
        """Exercise constituency-id-list option"""
        mock_ctor.return_value = None

        self.input_arguments['constituency_ids'] = [self.centers[0].constituency.id]

        call_command(self.command_name, self.phase,
                     constituency_ids=str(self.centers[0].constituency.id))

        mock_ctor.assert_called_once_with(self.phase, [self.centers[0]], self.input_arguments,
                                          self.username, ANY)
        self.assertTrue(mock_generate_rolls.called)

    def test_output_root_option(self, mock_generate_rolls, mock_ctor):
        """Exercise --output-root option"""
        mock_ctor.return_value = None

        output_root = '/ummm_like_wherever'

        call_command(self.command_name, self.phase, output_root=output_root)

        mock_ctor.assert_called_once_with(self.phase, self.centers, self.input_arguments,
                                          self.username, ANY)
        actual_output_path = mock_ctor.call_args[0][-1]
        # actual_output_path should be the root path that I passed plus a name generated by the
        # management command to which this code is not privy.
        if not actual_output_path.startswith(output_root + '/'):
            raise AssertionError
        self.assertGreater(len(actual_output_path), len(output_root + '/'))

        self.assertTrue(mock_generate_rolls.called)

    def test_output_root_default(self, mock_generate_rolls, mock_ctor):
        """Ensure --output-root option defaults to CWD"""
        mock_ctor.return_value = None

        call_command(self.command_name, self.phase)

        mock_ctor.assert_called_once_with(self.phase, self.centers, self.input_arguments,
                                          self.username, ANY)
        actual_output_path = mock_ctor.call_args[0][-1]

        # actual_output_path should be the CWD plus a name generated by the management command to
        # which this code is not privy.
        if not actual_output_path.startswith(os.getcwd() + '/'):
            raise AssertionError
        self.assertGreater(len(actual_output_path), len(os.getcwd() + '/'))

        self.assertTrue(mock_generate_rolls.called)

    def test_option_conflict(self, mock_generate_rolls, mock_ctor):
        """Ensure only one center/office option is accepted"""
        mock_ctor.return_value = None

        with self.assertRaises(CommandError) as cm:
            call_command(self.command_name, self.phase, center_ids=str(self.centers[0].center_id),
                         office_ids=str(self.centers[0].office.id))

        expected_message = 'Please specify at most one center/office/constituency id option.'
        self.assertEqual(cm.exception.message, expected_message)

        self.assertFalse(mock_ctor.called)
        self.assertFalse(mock_generate_rolls.called)

    def test_bad_center_id_rejected(self, mock_generate_rolls, mock_ctor):
        """ensure that a non-existent center id raises an error"""
        mock_ctor.return_value = None

        center_id = CENTER_ID_MAX_INT_VALUE

        self.input_arguments['center_ids'] = [center_id]

        with self.assertRaises(CommandError) as cm:
            call_command(self.command_name, self.phase, center_ids=str(center_id))

        expected_message = 'The following centers are not in the database: [{}].'.format(center_id)
        self.assertEqual(cm.exception.message, expected_message)

        self.assertFalse(mock_ctor.called)
        self.assertFalse(mock_generate_rolls.called)

    def test_bad_office_id_rejected(self, mock_generate_rolls, mock_ctor):
        """ensure that a non-existent office id raises an error"""
        mock_ctor.return_value = None

        office_id = 999999

        self.input_arguments['office_ids'] = [office_id]

        with self.assertRaises(CommandError) as cm:
            call_command(self.command_name, self.phase, office_ids=str(office_id))

        expected_message = 'The following offices are not in the database: [{}].'.format(office_id)
        self.assertEqual(cm.exception.message, expected_message)

        self.assertFalse(mock_ctor.called)
        self.assertFalse(mock_generate_rolls.called)

    def test_bad_constituency_id_rejected(self, mock_generate_rolls, mock_ctor):
        """ensure that a non-existent constituency id raises an error"""
        mock_ctor.return_value = None

        constituency_id = 999999

        self.input_arguments['constituency_ids'] = [constituency_id]

        with self.assertRaises(CommandError) as cm:
            call_command(self.command_name, self.phase, constituency_ids=str(constituency_id))

        expected_message = \
            'The following constituencies are not in the database: [{}].'.format(constituency_id)
        self.assertEqual(cm.exception.message, expected_message)

        self.assertFalse(mock_ctor.called)
        self.assertFalse(mock_generate_rolls.called)


class TestForgiveness(TestCase):
    """tests to test the --forgive-no-xxx options"""
    def setUp(self):
        self.username = os.environ.get('USER', 'unknown')
        self.command_name = 'generate_rolls'

        self.no_office, _ = Office.objects.get_or_create(id=NO_NAMEDTHING)
        self.no_office_center = RegistrationCenterFactory(office=self.no_office)
        self.center = RegistrationCenterFactory()
        self.copy_center = RegistrationCenterFactory(copy_of=self.center)

        self.phase = 'in-person'

        self.input_arguments = {'phase': self.phase,
                                'forgive_no_voters': False,
                                'forgive_no_office': False,
                                'office_ids': [],
                                'center_ids': [],
                                }

        # Each test gets a fresh work dir.
        self.output_path = tempfile.mkdtemp()

    def tearDown(self):
        # Clean up.
        shutil.rmtree(self.output_path)

    def test_no_office_center_not_forgiven_by_default(self):
        """ensure that a center that has no office raises an error without --forgive-no-office"""

        center_id = self.no_office_center.center_id
        self.input_arguments['center_ids'] = [center_id]

        with self.assertRaises(CommandError) as cm:
            call_command(self.command_name, self.phase, center_ids=str(center_id),
                         output_root=self.output_path)

        expected_message = \
            'The following centers have no associated office: [{}].'.format(center_id)
        self.assertEqual(cm.exception.message, expected_message)

    def test_no_office_center_can_be_forgiven(self):
        """ensure that a center that has no office is accepted when --forgive-no-office is True"""
        # Give it a registration so it doesn't raise an error.
        RegistrationFactory(registration_center=self.no_office_center, archive_time=None)
        center_id = self.no_office_center.center_id
        self.input_arguments['center_ids'] = [center_id]
        self.input_arguments['forgive_no_office'] = True

        call_command(self.command_name, self.phase, center_ids=str(center_id),
                     forgive_no_office=True, output_root=self.output_path)

        # No error raised

    def test_no_voter_center_not_forgiven_by_default(self):
        """ensure that a center that has no voters raises an error without --forgive-no-voters"""
        center_id = self.center.center_id
        self.input_arguments['center_ids'] = [center_id]

        with self.assertRaises(CommandError) as cm:
            call_command(self.command_name, self.phase, center_ids=str(center_id),
                         output_root=self.output_path)

        expected_message = 'The following centers have no registrants: [{}].'.format(center_id)
        self.assertEqual(cm.exception.message, expected_message)

    def test_no_voter_center_can_be_forgiven(self):
        """ensure that a center that has no voters is accepted when --forgive-no-voters=True"""
        center_id = self.center.center_id
        self.input_arguments['center_ids'] = [center_id]
        self.input_arguments['forgive_no_voters'] = True

        call_command(self.command_name, self.phase, center_ids=str(center_id),
                     forgive_no_voters=True, output_root=self.output_path)

        # No error raised

    def test_no_voter_copy_center_not_forgiven_by_default(self):
        """ensure that a center that's a copy of a center with no voters raises an error
        without --forgive-no-voters
        """
        center_id = self.copy_center.center_id
        self.input_arguments['center_ids'] = [center_id]

        with self.assertRaises(CommandError) as cm:
            call_command(self.command_name, self.phase, center_ids=str(center_id),
                         output_root=self.output_path)

        expected_message = 'The following centers have no registrants: [{}].'.format(center_id)
        self.assertEqual(cm.exception.message, expected_message)

    def test_copy_center_not_mistaken_for_no_registration_center(self):
        """ensure that a center that's a copy of a center with registrants is recognized as such"""
        RegistrationFactory(registration_center=self.center, archive_time=None)

        center_id = self.copy_center.center_id
        self.input_arguments['center_ids'] = [center_id]

        call_command(self.command_name, self.phase, center_ids=str(center_id),
                     output_root=self.output_path)

        # No error raised


class TestNoElectioNoRollgen(TestCase):
    """ensure that rollgen refuses to run if there's no election"""
    def setUp(self):
        self.username = os.environ.get('USER', 'unknown')
        self.command_name = 'generate_rolls'

        self.center = RegistrationCenterFactory()

        self.phase = 'polling'

        # Each test gets a fresh work dir.
        self.output_path = tempfile.mkdtemp()

    def tearDown(self):
        # Clean up.
        shutil.rmtree(self.output_path)

    def test_no_election_no_rollgen(self):
        """ensure that rollgen refuses to run if there's no election"""
        Election.objects.all().delete()

        with self.assertRaises(CommandError) as cm:
            call_command(self.command_name, self.phase, forgive_no_voters=True,
                         output_root=self.output_path)

        expected_message = 'There is no current in-person election.'
        self.assertEqual(cm.exception.message, expected_message)
