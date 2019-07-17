# -*- coding: utf-8 -*-

# Python imports
import logging
import os
from unittest.mock import patch

# Django imports
from django.test import TestCase
from django.utils.timezone import now

# Project imports
from .base import TestJobBase
from .factories import generate_arabic_place_name, create_voters, VoterFactory
from ..job import Job, get_voter_roll
from ..models import Station
from libya_elections.constants import MALE, FEMALE
from register.tests.factories import RegistrationCenterFactory


# Silence the logging output.
logger = logging.getLogger('rollgen')
logger.handlers = []
logger.addHandler(logging.NullHandler())


@patch('rollgen.job.generate_pdf_center_list')
@patch('rollgen.job.generate_pdf_station_book')
@patch('rollgen.job.generate_pdf_station_sign')
class TestGenerateRollsInPersonAndExhibitions(TestJobBase):
    """Exercise job.generate_rolls() for in-person and exhibitions phases.

    These phases are very similar so it makes sense to test them together.
    """
    def test_basic_in_person(self, mock_generate_pdf_station_sign, mock_generate_pdf_station_book,
                             mock_generate_pdf_center_list):
        """Test basic operation of the in_person phase."""
        phase = 'in-person'

        job = Job(phase, [self.center], self.input_arguments, self.user.username,
                  self.output_path)
        job.generate_rolls()

        # Ensure that the other PDF generation functions were not called.
        self.assertNotCalled((mock_generate_pdf_station_sign, mock_generate_pdf_station_book,
                              mock_generate_pdf_center_list))

        # Correct files and directories generated?
        expected_names = self.get_standard_manifest(phase)

        office_id = str(self.office_id)

        expected_names.append((office_id, 'dir'))

        filename = os.path.join(office_id, '{}_book_f.pdf'.format(self.center.center_id))
        expected_names.append((filename, 'file'))
        filename = os.path.join(office_id, '{}_book_m.pdf'.format(self.center.center_id))
        expected_names.append((filename, 'file'))

        self.assertExpectedNamesMatchActual(expected_names)

    def test_basic_exhibitions(self, mock_generate_pdf_station_sign, mock_generate_pdf_station_book,
                               mock_generate_pdf_center_list):
        """Test basic operation of the exhibitions phase."""
        phase = 'exhibitions'

        job = Job(phase, [self.center], self.input_arguments, self.user.username,
                  self.output_path)
        job.generate_rolls()

        # Ensure that the other PDF generation functions were not called.
        self.assertNotCalled((mock_generate_pdf_station_sign, mock_generate_pdf_station_book,
                              mock_generate_pdf_center_list))

        # Correct files and directories generated?
        expected_names = self.get_standard_manifest(phase)

        office_id = str(self.office_id)

        expected_names.append((office_id, 'dir'))

        filename = os.path.join(office_id, '{}_f.pdf'.format(self.center.center_id))
        expected_names.append((filename, 'file'))
        filename = os.path.join(office_id, '{}_m.pdf'.format(self.center.center_id))
        expected_names.append((filename, 'file'))

        self.assertExpectedNamesMatchActual(expected_names)


@patch('rollgen.job.generate_pdf')
class TestGenerateRollsPolling(TestJobBase):
    """Exercise job.generate_rolls() for polling phase."""
    def test_basic_polling(self, mock_generate_pdf):
        """Test basic operation of the polling phase."""
        phase = 'polling'

        job = Job(phase, [self.center], self.input_arguments, self.user.username, self.output_path)
        job.generate_rolls()

        # Ensure that the other PDF generation functions were not called.
        self.assertNotCalled((mock_generate_pdf,))

        # Correct files and directories generated?
        expected_names = self.get_standard_manifest(phase)

        office_id = str(self.office_id)

        expected_names.append((office_id, 'dir'))

        filename = os.path.join(office_id, '{}_1_book.pdf'.format(self.center.center_id))
        expected_names.append((filename, 'file'))
        filename = os.path.join(office_id, '{}_1_sign.pdf'.format(self.center.center_id))
        expected_names.append((filename, 'file'))
        filename = os.path.join(office_id, '{}_2_book.pdf'.format(self.center.center_id))
        expected_names.append((filename, 'file'))
        filename = os.path.join(office_id, '{}_2_sign.pdf'.format(self.center.center_id))
        expected_names.append((filename, 'file'))
        filename = os.path.join(office_id, '{}_f_list.pdf'.format(self.center.center_id))
        expected_names.append((filename, 'file'))
        filename = os.path.join(office_id, '{}_m_list.pdf'.format(self.center.center_id))
        expected_names.append((filename, 'file'))

        self.assertExpectedNamesMatchActual(expected_names)

    def test_simple_station_creation_and_overwriting(self, mock_generate_pdf):
        """Ensure that stations are created and overwritten as appropriate"""
        phase = 'polling'

        job = Job(phase, [self.center], self.input_arguments, self.user.username, self.output_path)
        job.generate_rolls()

        # one male and one female station should have been created
        stations = Station.objects.all()
        self.assertEqual(len(stations), 2)
        gender_counts = {MALE: 0, FEMALE: 0}
        for station in stations:
            self.assertEqual(station.center, self.center)
            gender_counts[station.gender] += 1
        self.assertEqual(list(gender_counts.values()), [1, 1])

        first_set_of_station_ids = set([station.id for station in stations])

        # Now create new stations for that center and verify that the old ones get deleted
        job = Job(phase, [self.center], self.input_arguments, self.user.username, self.output_path)
        job.generate_rolls()

        # one male and one female station should have been created
        stations = Station.objects.all()
        self.assertEqual(len(stations), 2)
        gender_counts = {MALE: 0, FEMALE: 0}
        for station in stations:
            self.assertEqual(station.center, self.center)
            gender_counts[station.gender] += 1
        self.assertEqual(list(gender_counts.values()), [1, 1])

        second_set_of_station_ids = set([station.id for station in stations])

        self.assertTrue(first_set_of_station_ids.isdisjoint(second_set_of_station_ids))


@patch('rollgen.job.generate_pdf')
class TestSelectiveStationCreationAndOverwriting(TestJobBase):
    """Ensure that stations are created and overwritten as appropriate.

    This runs three jobs and involves multiple centers. It's in its own class because it
    mangles some self.attrs that might confuse other tests.
    """
    def test_complex_station_creation_and_overwriting(self, mock_generate_pdf):
        """Ensure that stations are created and overwritten as appropriate"""
        phase = 'polling'

        job = Job(phase, [self.center], self.input_arguments, self.user.username, self.output_path)
        job.generate_rolls()

        # one male and one female station should have been created
        stations = Station.objects.all()
        self.assertEqual(len(stations), 2)
        gender_counts = {MALE: 0, FEMALE: 0}
        for station in stations:
            self.assertEqual(station.center, self.center)
            gender_counts[station.gender] += 1
        self.assertEqual(list(gender_counts.values()), [1, 1])

        first_set_of_station_ids = set([station.id for station in stations])

        # Create a second center and run a second job for that center.
        center2 = RegistrationCenterFactory()
        create_voters(3, gender=MALE, center=center2)
        self.input_arguments['center_ids'] = [center2.center_id]

        job = Job(phase, [center2], self.input_arguments, self.user.username, self.output_path)
        job.generate_rolls()

        # one new male station should have been created, plus the stations created a moment ago
        # should still be around.
        stations = Station.objects.all()
        self.assertEqual(len(stations), 3)

        stations = Station.objects.filter(center=self.center)
        self.assertEqual(len(stations), 2)
        gender_counts = {MALE: 0, FEMALE: 0}
        for station in stations:
            self.assertEqual(station.center, self.center)
            gender_counts[station.gender] += 1
        self.assertEqual(list(gender_counts.values()), [1, 1])
        self.assertEqual(set([station.id for station in stations]), first_set_of_station_ids)

        stations = Station.objects.filter(center=center2)
        self.assertEqual(len(stations), 1)
        station = stations[0]
        self.assertEqual(station.gender, MALE)

        second_job_station_id = station.id

        # Create a third center and run a third job for the 2nd & 3rd center. That should
        # overwrite the stations for the 2nd center and create new stations for the 3rd center.
        center3 = RegistrationCenterFactory()
        create_voters(3, gender=MALE, center=center3)
        self.input_arguments['center_ids'] = [center2.center_id, center3.center_id, ]

        job = Job(phase, [center2, center3], self.input_arguments, self.user.username,
                  self.output_path)
        job.generate_rolls()

        # There should be 4 stations now, 2 from the first job, 1 from the second (just got
        # overwritten by that last job), and 1 from the third (most recent) job.
        stations = Station.objects.all()
        self.assertEqual(len(stations), 4)

        stations = Station.objects.filter(center=self.center)
        self.assertEqual(len(stations), 2)
        gender_counts = {MALE: 0, FEMALE: 0}
        for station in stations:
            gender_counts[station.gender] += 1
        self.assertEqual(list(gender_counts.values()), [1, 1])
        self.assertEqual(set([station.id for station in stations]), first_set_of_station_ids)

        stations = Station.objects.filter(center=center2)
        self.assertEqual(len(stations), 1)
        station = stations[0]
        self.assertEqual(station.gender, MALE)
        # station created previously for this center should not exist anymore
        with self.assertRaises(Station.DoesNotExist):
            Station.objects.get(pk=second_job_station_id)

        stations = Station.objects.filter(center=center3)
        self.assertEqual(len(stations), 1)
        station = stations[0]
        self.assertEqual(station.gender, MALE)


class TestGetVoterRoll(TestCase):
    """Exercise job.get_voter_roll()"""
    def setUp(self):
        self.center = RegistrationCenterFactory(name=generate_arabic_place_name())

        self.center_with_a_copy = RegistrationCenterFactory(name=generate_arabic_place_name())

        self.copy_center = RegistrationCenterFactory(name=generate_arabic_place_name(),
                                                     copy_of=self.center_with_a_copy)

        # Create an unused center just to clutter things up a bit.
        self.unused_center = RegistrationCenterFactory(name=generate_arabic_place_name())

        # Create a few voters and register them at each of these centers (except the copy center
        # because voters can't register at copy centers).
        self.n_voters = 3

        archive_time = now()

        self.voters = {}
        for center in (self.center, self.center_with_a_copy, self.unused_center):
            self.voters[center] = create_voters(self.n_voters, FEMALE, center)
            # Also create an archived registration for each center to ensure that
            # get_voter_roll() ignores it.
            voter = VoterFactory(post__center=center)
            registration = voter.registration
            registration.archive_time = archive_time
            registration.save()

    def test_get_voter_roll_simple_center(self):
        """exercise get_voter_roll() for a center with no copy complications"""
        voters = list(get_voter_roll(self.center))
        self.assertEqual(voters, self.voters[self.center])

    def test_get_voter_roll_copied_center(self):
        """exercise get_voter_roll() for a center with a copy"""
        voters = list(get_voter_roll(self.center_with_a_copy))
        self.assertEqual(voters, self.voters[self.center_with_a_copy])

    def test_get_voter_roll_copy_center(self):
        """exercise get_voter_roll() for a center that is a copy"""
        voters = list(get_voter_roll(self.copy_center))
        self.assertEqual(voters, self.voters[self.center_with_a_copy])
