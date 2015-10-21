# Python imports
from __future__ import unicode_literals
from __future__ import division
import cStringIO as StringIO
import csv
import datetime
import logging
import os

# 3rd party imports
from mock import ANY

# Django imports
from django.utils.timezone import now as django_now

# Project imports
from .base import TestJobBase
from ..job import Job
from ..models import Station, station_distributor
from ..utils import generate_polling_metadata_csv, GENDER_NAMES
from libya_elections.constants import FEMALE
from register.models import RegistrationCenter
from register.tests.factories import RegistrationCenterFactory
from voting.tests.factories import ElectionFactory

# Silence the logging output.
logger = logging.getLogger('rollgen')
logger.handlers = []
logger.addHandler(logging.NullHandler())


class TestPollingCSVs(TestJobBase):
    """The polling phase creates 3 CSVs; this tests that they have the correct content."""

    def setUp(self):
        super(TestPollingCSVs, self).setUp()
        # Jam a comma in one of the fields that appears in the CSV to exercise the code's
        # ability to escape the delimiter correctly.
        self.center.name = ',' + self.center.name
        self.center.save()
        job = Job('polling', [self.center], self.input_arguments, self.user.username,
                  self.output_path)
        job.generate_rolls()

        # Create a station related to an older election in a (hopefully unsuccessful) attempt to
        # confuse the code that creates the polling metadata CSV.
        start = django_now()
        start = start.replace(year=start.year - 1)
        end = start.replace(year=start.year - 1) + datetime.timedelta(days=1)
        old_election = ElectionFactory(polling_start_time=start, polling_end_time=end)
        old_center = RegistrationCenterFactory()
        Station(election=old_election, center=old_center, number=1, gender=FEMALE,
                n_registrants=42, first_voter_name='first', first_voter_number=1,
                last_voter_name='last', last_voter_number=42)

    def test_voter_info_csvs(self):
        """Test that the polling-specific voter info CSVs contain the correct content."""
        header = [['national_id', 'center_id', 'station_number']]

        filename = 'voters_by_national_id.csv'
        with open(os.path.join(self.output_path, filename), 'rb') as f:
            actual_lines = [line for line in csv.reader(f)]

        stations = station_distributor(self.voters)

        center_id = str(self.center.center_id)
        voter_stations = [[str(voter.national_id), center_id, str(station.number)]
                          for station in stations for voter in station.roll]
        voter_stations.sort()

        self.assertEqual(header + voter_stations, actual_lines)

        filename = 'voters_by_center_and_station.csv'

        with open(os.path.join(self.output_path, filename), 'rb') as f:
            actual_lines = [line for line in csv.reader(f)]

        voter_stations = sorted(voter_stations, key=lambda voter_station: voter_station[1:])

        self.assertEqual(header + voter_stations, actual_lines)

    def test_polling_metadata_csv(self):
        """Test that the polling-specific metadata CSV contains the correct content."""
        faux_file = StringIO.StringIO()
        faux_file.write(generate_polling_metadata_csv())
        faux_file.seek(0)
        actual_lines = [line for line in csv.reader(faux_file)]

        stations = Station.objects.all()

        # Expected lines are a header + 2 data rows. The data rows contain precise timestamps that
        # I match to mock's ANY for the first crude comparion. Later I check them to make sure
        # they're reasonably accurate.
        expected_lines = [['Centre #', 'Centre Name', 'Centre Type', 'Office #', 'Constituency #',
                           'Constituency Name', 'SubConstituency #', 'SubConstituency Name',
                           'Station number', 'Station Gender', 'Number of Registrants',
                           'First Name', 'First Name Number', 'Last Name', 'Last Name Number',
                           'When Generated']]

        # First data row
        station = stations[0]
        line = [str(self.center.center_id),
                self.center.name.encode('utf-8'),
                RegistrationCenter.Types.NAMES['ar'][self.center.center_type].encode('utf-8'),
                str(self.center.office_id),
                str(self.center.constituency_id),
                self.center.constituency.name_arabic.encode('utf-8'),
                str(self.center.subconstituency.id),
                self.center.subconstituency.name_arabic.encode('utf-8'),
                str(station.number),
                GENDER_NAMES[station.gender],
                str(station.n_registrants),
                station.first_voter_name.encode('utf-8'),
                str(station.first_voter_number),
                station.last_voter_name.encode('utf-8'),
                str(station.last_voter_number),
                ANY]
        expected_lines.append(line)

        # Second data row
        station = stations[1]
        line = [str(self.center.center_id),
                self.center.name.encode('utf-8'),
                RegistrationCenter.Types.NAMES['ar'][self.center.center_type].encode('utf-8'),
                str(self.center.office_id),
                str(self.center.constituency_id),
                self.center.constituency.name_arabic.encode('utf-8'),
                str(self.center.subconstituency.id),
                self.center.subconstituency.name_arabic.encode('utf-8'),
                str(station.number),
                GENDER_NAMES[station.gender],
                str(station.n_registrants),
                station.first_voter_name.encode('utf-8'),
                str(station.first_voter_number),
                station.last_voter_name.encode('utf-8'),
                str(station.last_voter_number),
                ANY]

        expected_lines.append(line)

        self.assertEqual(expected_lines, actual_lines)

        for line in actual_lines[1:]:
            now = django_now()
            timestamp = line[-1]
            timestamp = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            timestamp = timestamp.replace(tzinfo=now.tzinfo)
            delta = now - timestamp
            self.assertGreaterEqual(60, delta.total_seconds())
