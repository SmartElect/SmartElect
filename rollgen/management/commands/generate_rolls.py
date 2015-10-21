# Python imports
from __future__ import unicode_literals
from __future__ import division
import os
import logging
from optparse import make_option

# 3rd party imports


# Django imports
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError

# Project imports
from register.models import RegistrationCenter, Office, Constituency
from rollgen.utils import validate_comma_delimited_ids, find_invalid_center_ids, \
    get_job_name, read_ids, handle_job_exception
from rollgen.job import Job, PHASES

logger = logging.getLogger('rollgen')

stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
logger.addHandler(stream_handler)


class Command(BaseCommand):
    """Django mgmt command for running the roll generator."""

    args = '<phase>'

    FORGIVE_NO_OFFICE_DEFAULT = False
    FORGIVE_NO_VOTERS_DEFAULT = False
    FORGIVE_NO_OFFICE_HELP = "Process centers even if they have no associated office "
    FORGIVE_NO_OFFICE_HELP += ("(default={})".format(FORGIVE_NO_OFFICE_DEFAULT))
    FORGIVE_NO_VOTERS_HELP = "Process centers even if they have no voters "
    FORGIVE_NO_VOTERS_HELP += ("(default={})".format(FORGIVE_NO_VOTERS_DEFAULT))

    option_list = BaseCommand.option_list + (
        make_option('--center-id-file',
                    action='store',
                    dest='center_id_file',
                    default=None,
                    help='A file containing a list of center ids to process'),
        make_option('--center-id-list',
                    action='store',
                    dest='center_ids',
                    default=None,
                    help='A comma-delimited list of center ids to process (no spaces)'),
        make_option('--office-id-file',
                    action='store',
                    dest='office_id_file',
                    default=None,
                    help='A file containing a list of office ids to process'),
        make_option('--office-id-list',
                    action='store',
                    dest='office_ids',
                    default=None,
                    help='A comma-delimited list of office ids to process (no spaces)'),
        make_option('--constituency-id-file',
                    action='store',
                    dest='constituency_id_file',
                    default=None,
                    help='A file containing a list of constituency ids to process'),
        make_option('--constituency-id-list',
                    action='store',
                    dest='constituency_ids',
                    default=None,
                    help='A comma-delimited list of constituency ids to process (no spaces)'),
        make_option('--output-root',
                    action='store',
                    dest='output_root',
                    default=None,
                    help='The root directory for the output (defaults to current directory)'),
        make_option('--forgive-no-office',
                    action='store_true',
                    dest='forgive_no_office',
                    default=FORGIVE_NO_OFFICE_DEFAULT,
                    help=FORGIVE_NO_OFFICE_HELP),
        make_option('--forgive-no-voters',
                    action='store_true',
                    dest='forgive_no_voters',
                    default=False,
                    help=FORGIVE_NO_VOTERS_HELP),
        )

    def handle(self, *args, **options):
        valid_phases = PHASES.keys()

        if len(args) != 1:
            msg = 'Please specify exactly one of the following phases: ' + ', '.join(valid_phases)
            raise CommandError(msg)

        phase = args[0].lower()
        if phase not in valid_phases:
            valid_phases = ', '.join(valid_phases)
            raise CommandError('Phase must be one of {phases}'.format(phases=valid_phases))

        # Ensure center specification options don't conflict
        center_options = ('center_id_file', 'center_ids', 'office_id_file', 'office_ids',
                          'constituency_id_file', 'constituency_ids', )
        center_options = [1 if options[name] else 0 for name in center_options]
        if sum(center_options) > 1:
            raise CommandError('Please specify at most one center/office/constituency id option.')

        center_ids = []
        office_ids = []
        constituency_ids = []

        # Was --center-id-list option specified?
        if options['center_ids']:
            center_ids = options['center_ids'].split(',')

        # Was --center-id-file option specified?
        if options['center_id_file']:
            center_ids = read_ids(options['center_id_file'])

        if center_ids:
            # One of the two --center-id-xxx options was specified
            try:
                validate_comma_delimited_ids(center_ids, True)
            except ValidationError:
                raise CommandError("At least one of the center ids is not valid.")

            center_ids = map(int, center_ids)
            invalid_center_ids = find_invalid_center_ids(center_ids)

            if invalid_center_ids:
                msg = "The following centers are not in the database: {}."
                raise CommandError(msg.format(invalid_center_ids))

        # Was the --office-id-list option specified?
        if options['office_ids']:
            office_ids = options['office_ids'].split(',')

        # Was the --office-id-file option specified?
        if options['office_id_file']:
            office_ids = read_ids(options['office_id_file'])

        if office_ids:
            # One of the two --office-id-xxx options was specified
            try:
                validate_comma_delimited_ids(office_ids)
            except ValidationError:
                raise CommandError("At least one of the office ids is not valid.")

            office_ids = map(int, office_ids)

            offices = Office.objects.filter(id__in=office_ids)

            valid_office_ids = [office.id for office in offices]

            invalid_office_ids = [id_ for id_ in office_ids if id_ not in valid_office_ids]

            if invalid_office_ids:
                msg = "The following offices are not in the database: {}."
                raise CommandError(msg.format(invalid_office_ids))

        # Was the --constituency-id-list option specified?
        if options['constituency_ids']:
            constituency_ids = options['constituency_ids'].split(',')

        # Was the --constituency-id-file option specified?
        if options['constituency_id_file']:
            constituency_ids = read_ids(options['constituency_id_file'])

        if constituency_ids:
            # One of the two --constituency-id-xxx options was specified
            try:
                validate_comma_delimited_ids(constituency_ids)
            except ValidationError:
                raise CommandError("At least one of the constituency ids is not valid.")

            constituency_ids = map(int, constituency_ids)

            constituencies = Constituency.objects.filter(id__in=constituency_ids)

            valid_constituency_ids = [constituency.id for constituency in constituencies]

            invalid_constituency_ids = [id_ for id_ in constituency_ids if id_ not in
                                        valid_constituency_ids]

            if invalid_constituency_ids:
                msg = "The following constituencies are not in the database: {}."
                raise CommandError(msg.format(invalid_constituency_ids))

        if center_ids:
            centers = RegistrationCenter.objects.filter(center_id__in=center_ids)
        elif office_ids:
            centers = RegistrationCenter.objects.filter(office_id__in=office_ids)
        elif constituency_ids:
            centers = RegistrationCenter.objects.filter(constituency_id__in=constituency_ids)
        else:
            centers = RegistrationCenter.objects.all()

        centers = centers.filter(reg_open=True).prefetch_related('office')

        # Converting centers from a queryset to a list isn't necessary, but it makes testing easier
        # because I can ask mock to compare Job.__init__() call args to simple lists instead of
        # constructing querysets.
        centers = list(centers)

        if not centers:
            raise CommandError("The criteria you provided match no active centers.")

        username = os.environ.get('USER', 'unknown')

        output_path = os.path.join((options['output_root'] or os.getcwd()), get_job_name(username))
        output_path = os.path.expanduser(output_path)

        input_arguments = {'phase': phase,
                           'forgive_no_voters': options['forgive_no_voters'],
                           'forgive_no_office': options['forgive_no_office'],
                           'office_ids': office_ids,
                           'center_ids': center_ids,
                           'constituency_ids': constituency_ids,
                           }

        job = Job(phase, centers, input_arguments, username, output_path)

        # Ready to roll! (ha ha, get it?)
        try:
            job.generate_rolls()
        except Exception as exception:
            handle_job_exception(exception, job.output_path)

            raise CommandError(str(exception))
