from datetime import datetime

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from pytz import timezone

from reporting_api.create_test_data import create, DEFAULT_NUM_COPY_CENTERS, \
    DEFAULT_NUM_DAILY_REPORTS, DEFAULT_NUM_INACTIVE_PER_ELECTION, \
    DEFAULT_NUM_NO_REG_CENTERS, DEFAULT_NUM_REGISTRATION_CENTERS, \
    DEFAULT_NUM_REGISTRATION_DATES, DEFAULT_NUM_REGISTRATIONS, \
    DEFAULT_NUM_SUBCONSTITUENCIES

DELETE_EXISTING_DATA_ARG = '--yes-delete-my-data'
DELETE_EXISTING_DATA_OPT = 'yes_delete_my_data'  # as an option key


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            DELETE_EXISTING_DATA_ARG, action='store_true',
            default=False,
            help='Remove existing data first')
        parser.add_argument(
            '--center-without-office', action='store_true',
            help='Make sure there is at least one center which is not in an office')
        parser.add_argument(
            '--num-registrations',
            default=DEFAULT_NUM_REGISTRATIONS,
            type=int,
            help='Specify the number of registrations to create')
        parser.add_argument(
            '--num-registration-dates',
            default=DEFAULT_NUM_REGISTRATION_DATES,
            type=int,
            help='Specify the number of dates with registrations')
        parser.add_argument(
            '--num-centers',
            default=DEFAULT_NUM_REGISTRATION_CENTERS,
            type=int,
            help='Distribute registrations among this number of registration centers')
        parser.add_argument(
            '--num-copy-centers',
            default=DEFAULT_NUM_COPY_CENTERS,
            type=int,
            help='Create copies of some centers used for registrations')
        parser.add_argument(
            '--num-daily-reports',
            default=DEFAULT_NUM_DAILY_REPORTS,
            type=int,
            help='Number of daily reports')
        parser.add_argument(
            '--num-subconstituencies',
            default=DEFAULT_NUM_SUBCONSTITUENCIES,
            type=int,
            help='Distribute registrations among this number of subconstituencies')
        parser.add_argument(
            '--use-existing-infra', action='store_true',
            default=False,
            help='Use existing Offices, Constituencies, SubConstituencies, etc.')
        parser.add_argument(
            '--election-dates',
            default=(),
            help='List of comma-separated election dates in the form YYYY-MM-DD')
        parser.add_argument(
            '--num-inactive-per-election',
            default=DEFAULT_NUM_INACTIVE_PER_ELECTION,
            type=int,
            help='Mark some number of centers as inactive for each created election')
        parser.add_argument(
            '--num-no-reg-centers',
            default=DEFAULT_NUM_NO_REG_CENTERS,
            type=int,
            help='Mark some number of centers as not supporting registrations')

    def handle(self, *args, **options):
        if not options.pop(DELETE_EXISTING_DATA_OPT, False):
            raise CommandError("%s is a required parameter" % DELETE_EXISTING_DATA_ARG)
        election_dates = []
        if options['election_dates']:
            tz = timezone(settings.TIME_ZONE)
            for date_str in options['election_dates'].split(','):
                election_dates.append(
                    tz.localize(datetime.strptime(date_str, '%Y-%m-%d'))
                )

        return create(center_without_office=options['center_without_office'],
                      num_registrations=options['num_registrations'],
                      num_registration_dates=options['num_registration_dates'],
                      num_daily_reports=options['num_daily_reports'],
                      num_registration_centers=options['num_centers'],
                      num_copy_centers=options['num_copy_centers'],
                      num_subconstituencies=options['num_subconstituencies'],
                      use_existing_infra=options['use_existing_infra'],
                      num_inactive_centers_per_election=options['num_inactive_per_election'],
                      num_no_reg_centers=options['num_no_reg_centers'],
                      election_dates=election_dates)
