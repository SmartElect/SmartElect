# Python imports
from __future__ import division
from __future__ import unicode_literals
import os
import logging
import hashlib
from collections import Counter, namedtuple
import zipfile
import json

# Django imports
from django.conf import settings
from django.db import transaction
from django.forms.models import model_to_dict
from django.utils.timezone import now as django_now

# 3rd party imports

# Project imports
from .constants import METADATA_FILENAME, ROLLGEN_FLAG_FILENAME, ROLLGEN_FLAG_FILENAME_CONTENT, \
    CITIZEN_SORT_FIELDS
from .generate_pdf import generate_pdf
from .generate_pdf_ed import generate_pdf_center_list, generate_pdf_station_book, \
    generate_pdf_station_sign
from .models import Station, station_distributor
from .utils import out_of_disk_space_handler_context, NoVotersError, NoOfficeError, NoElectionError
from civil_registry.models import Citizen
from libya_elections.constants import NO_NAMEDTHING, MALE, FEMALE, GENDER_ABBRS
from libya_elections.csv_utils import UnicodeWriter
from register.models import Registration, RegistrationCenter
from voting.models import Election

logger = logging.getLogger(__name__)

# These are the 3 valid roll generation phases.
PHASES = {'in-person': 'In Person',
          'exhibitions': 'Exhibitions',
          'polling': 'Polling',
          }


INPUT_ARGUMENTS_TEMPLATE = {'phase': '',
                            'forgive_no_voters': False,
                            'forgive_no_office': False,
                            'office_ids': [],
                            'center_ids': [],
                            'constituency_ids': [],
                            }

# VoterStation allows me to collect info about which voters are at which center and station.
# I'll promote it to a class if that seems beneficial at some point. Right now tuples are easier
# to sort.
VoterStation = namedtuple('VoterStation', ['national_id', 'center_id', 'station_number', ])


class Job(object):
    """Defines a rollgen job and allows one to execute it."""

    # FILENAME_TEMPLATES defines how each phase's filenames are formed. See get_filename().
    FILENAME_TEMPLATES = {'in-person': '{center_id}_book_{gender}.pdf',
                          'exhibitions': '{center_id}_{gender}.pdf',
                          'polling_list': '{center_id}_{gender}_list.pdf',
                          'polling_book': '{center_id}_{station_number}_book.pdf',
                          'polling_sign': '{center_id}_{station_number}_sign.pdf',
                          }

    def __init__(self, phase, centers, input_arguments, user, output_path):
        """Create a job.

        phases must be one of PHASES.keys().
        centers must be a list of one or more RegistrationCenter instances
        input_arguments must be a dict in the form of INPUT_ARGUMENTS_TEMPLATE
        user is a string identifying the user running this job
        output_path is a directory name defining where output will be written

        The office on each center is used during processing, so callers can improve performance by
        using .prefetch_related('office') when building the centers queryset.
        """
        # Phase, centers, output_path, input_arguments, and user are set here in __init__() and
        # don't change hereafter.
        self.phase = phase
        self.centers = centers
        self.output_path = output_path
        self.input_arguments = input_arguments
        self.user = user

        # The begin and end timestamps are set by generate_rolls()
        self.begin = None
        self.end = None

        # These are populated as the rolls are generated.
        self.voter_stations = []
        self.fileinfo = {}
        self.n_total_pages = 0
        self.n_total_bytes = 0
        # self.offices maps office ids to Office instances
        self.offices = {}

        # FIXME if the output path exists, this should probably raise an error
        if not os.path.exists(self.output_path):
            with out_of_disk_space_handler_context():
                os.makedirs(self.output_path)

        with open(os.path.join(self.output_path, ROLLGEN_FLAG_FILENAME), 'w') as f:
            f.write(ROLLGEN_FLAG_FILENAME_CONTENT)

    @property
    def n_total_files(self):
        """Return # of total PDFs created. CSVs and other metadata files are not counted."""
        return len(self.fileinfo)

    @property
    def elapsed(self):
        """Return # of seconds spent generating rolls.

        Raises an error if accessed before roll generation is complete.
        """
        if self.begin and self.end:
            return (self.end - self.begin).total_seconds()
        else:
            raise ValueError

    def add(self, filename, n_pages):
        """Given a PDF filename and the number of pages in that PDF, add it to the tracker dict."""
        content = open(filename, 'rb').read()
        size = len(content)

        # Before storing the filename I strip first part of output path which is the parent
        # directory of all of these files. We don't want that info in here because it will become
        # wrong if these files are ever moved, and we want them to be relocatable without
        # breaking anything.
        filename = os.path.relpath(filename, self.output_path)

        self.fileinfo[filename] = {'n_pages': n_pages,
                                   'size': size,
                                   'hash': hashlib.sha256(content).hexdigest(),
                                   }

        self.n_total_pages += n_pages
        self.n_total_bytes += size

    @property
    def metadata(self):
        """Return job metadata. Relies on elapsed (q.v.)"""
        metadata = {}
        metadata['successful'] = True
        metadata['time_information'] = {'begin': self.begin.isoformat(),
                                        'end': self.end.isoformat(),
                                        'elapsed': self.elapsed,
                                        }
        metadata['user'] = self.user
        metadata['database'] = {'name': settings.DATABASES['default']['NAME'],
                                'host': settings.DATABASES['default']['HOST'],
                                }
        metadata['input_arguments'] = self.input_arguments
        center_ids = [center.center_id for center in self.centers]
        metadata['registration_centers_processed'] = sorted(center_ids)
        metadata['total_pdf_file_count'] = self.n_total_files
        metadata['total_pdf_page_count'] = self.n_total_pages
        metadata['total_pdf_byte_count'] = self.n_total_bytes
        metadata['files'] = self.fileinfo
        metadata['offices'] = [model_to_dict(office) for office in self.offices.values()]

        return metadata

    def get_filename(self, path, params, type_=None):
        """Return the phase-appropriate fully qualified filename.

        The filename is populated with the passed params. type_ is only appropriate when the
        phase is polling, and should be one of 'list', 'book', or 'sign'.
        """
        phase = self.phase

        if type_:
            phase += ('_' + type_)

        filename = self.FILENAME_TEMPLATES[phase].format(**params)

        return os.path.join(path, filename)

    def generate_rolls(self):
        """Build PDFs for this job. This is where all the action happens.

        May raise NoVotersError, NoOfficeError and OutOfDiskSpaceError.
        """
        self.begin = django_now()

        if not self.input_arguments['forgive_no_office']:
            # We are not going to be forgiving if we find any office-less centers.
            has_office = lambda center: center.office.id != NO_NAMEDTHING
            problem_centers = [center.center_id for center in self.centers if not
                               has_office(center)]

            if problem_centers:
                msg = "The following centers have no associated office: {}."
                raise NoOfficeError(msg.format(problem_centers))

        if not self.input_arguments['forgive_no_voters']:
            # Test each center to make sure it has at least one registration. This is a lot of
            # DB churn and can take a while. It has to be done in two parts.

            # Find non-copy centers with no registrations
            problem_center_ids = \
                RegistrationCenter.objects.filter(id__in=[center.id for center in self.centers],
                                                  registration__isnull=True,
                                                  copy_of_id__isnull=True).values_list('id',
                                                                                       flat=True)
            problem_centers = [center for center in self.centers if center.id in problem_center_ids]

            # Find copy centers with no registrations. This runs one query per center which is
            # the expensive way to do it, but it's the only way to figure out exactly which copy
            # centers (if any) have parents with no registrations without dropping to raw SQL.
            for center in self.centers:
                copied = center.copy_of
                if copied:
                    if not Registration.objects.filter(registration_center=copied).exists():
                        problem_centers.append(center)

            if problem_centers:
                problem_centers = [center.center_id for center in problem_centers]
                msg = "The following centers have no registrants: {}."
                raise NoVotersError(msg.format(problem_centers))

        for i_center, center in enumerate(self.centers):
            # Fetch the voters for this center from the DB.
            voter_roll = get_voter_roll(center)

            office_id = center.office.id
            if office_id not in self.offices:
                self.offices[office_id] = center.office

            out_path = os.path.join(self.output_path, str(office_id))
            if not os.path.exists(out_path):
                with out_of_disk_space_handler_context():
                    os.makedirs(out_path)

            filename_params = {'center_id': center.center_id, }

            # Generate different PDFs based on phase
            if self.phase == 'in-person':
                # election center books only
                for gender in (FEMALE, MALE):
                    filename_params['gender'] = GENDER_ABBRS[gender]
                    filename = self.get_filename(out_path, filename_params)
                    n_pages = generate_pdf(filename, center, voter_roll, gender, center_book=True)
                    self.add(filename, n_pages)

            elif self.phase == 'exhibitions':
                # election center list only
                for gender in (FEMALE, MALE):
                    filename_params['gender'] = GENDER_ABBRS[gender]
                    filename = self.get_filename(out_path, filename_params)
                    n_pages = generate_pdf(filename, center, voter_roll, gender)
                    self.add(filename, n_pages)

            elif self.phase == 'polling':
                # distribute registrations into stations for this center
                stations = station_distributor(voter_roll)

                # Stash the list of which voters registered at this center/station for later.
                election = Election.objects.get_most_current_election()
                if not election:
                    raise NoElectionError('There is no current in-person election.')
                for station in stations:
                    station.election = election
                    station.center = center
                    for voter in station.roll:
                        voter_station = VoterStation(national_id=voter.national_id,
                                                     center_id=center.center_id,
                                                     station_number=station.number)
                        self.voter_stations.append(voter_station)

                # count stations by gender for center list
                station_counts_by_gender = Counter(station.gender for station in stations)
                for gender in station_counts_by_gender:
                    filename_params['gender'] = GENDER_ABBRS[gender]
                    filename = self.get_filename(out_path, filename_params, 'list')
                    n_pages = generate_pdf_center_list(filename, stations, gender)
                    self.add(filename, n_pages)
                    logger.info('center list {}'.format(filename))

                # Create a separate book and sign for each station
                for station in stations:
                    filename_params['station_number'] = station.number

                    # polling station books
                    filename = self.get_filename(out_path, filename_params, 'book')
                    n_pages = generate_pdf_station_book(filename, station)
                    self.add(filename, n_pages)
                    logger.info('station book {}'.format(filename))

                    # polling station sign
                    filename = self.get_filename(out_path, filename_params, 'sign')
                    n_pages = generate_pdf_station_sign(filename, station)
                    self.add(filename, n_pages)
                    logger.info('station book {}'.format(filename))

                with transaction.atomic():
                    # Delete any existing Stations for this center and replace them with new.
                    Station.objects.filter(election=election, center=center).delete()
                    for station in stations:
                        station.save()

            # Emit status
            logger.info('saved PDFs for center %s' % center.center_id)
            params = (i_center + 1, len(self.centers), (i_center + 1) / len(self.centers))
            logger.info("Completed {} of {} (~{:.2%})".format(*params))

        self.end = django_now()

        # Now that rolls are generated, write voter station CSVs (if appropriate) and job JSON
        # metadata. Last but not least, zip output.
        if self.voter_stations:
            # Write voter station data twice to CSV files. First sorted by national id and again
            # sorted by (center id, station number).
            header = [('national_id', 'center_id', 'station_number')]
            # sort by national id
            self.voter_stations.sort()

            filename = os.path.join(self.output_path, 'voters_by_national_id.csv')
            with out_of_disk_space_handler_context():
                csv_writer = UnicodeWriter(open(filename, 'w'))
                csv_writer.writerows(header)
                csv_writer.writerows(self.voter_stations)

            # sort by center, station number
            self.voter_stations.sort(key=lambda voter_station: voter_station[1:])

            filename = os.path.join(self.output_path, 'voters_by_center_and_station.csv')
            with out_of_disk_space_handler_context():
                csv_writer = UnicodeWriter(open(filename, 'w'))
                csv_writer.writerows(header)
                csv_writer.writerows(self.voter_stations)

        # Write the JSON metadata file
        metadata_filename = os.path.join(self.output_path, METADATA_FILENAME)
        with out_of_disk_space_handler_context():
            with open(metadata_filename, 'w') as f:
                json.dump(self.metadata, f, indent=2)

        # Write a hash of the metadata file
        sha = hashlib.sha256(open(metadata_filename).read()).hexdigest()
        with out_of_disk_space_handler_context():
            open(metadata_filename + '.sha256', 'w').write(sha)

        logger.info('zipping output')
        for office_id in sorted(self.offices.keys()):
            office_dir = os.path.join(self.output_path, str(office_id))
            with out_of_disk_space_handler_context():
                zip_filename = office_dir + '.zip'
                with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as office_zip:
                    logger.info('zipping %s' % office_dir)
                    for office_base, dirs, files in os.walk(office_dir):
                        for pdf in files:
                            fn = os.path.join(office_base, pdf)
                            office_zip.write(fn, pdf)

        logger.info('done')


def get_voter_roll(center):
    """Given a center, return a name-sorted list of the registrants for that center
    as a Citizen queryset."""
    if center.copy_of:
        center = center.copy_of

    return Citizen.objects.filter(registrations__registration_center_id=center.id,
                                  registrations__archive_time=None).order_by(*CITIZEN_SORT_FIELDS)
