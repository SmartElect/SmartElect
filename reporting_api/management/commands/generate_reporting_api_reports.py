from django.core.management import BaseCommand
from reporting_api.reports import generate_registrations_reports, \
    generate_election_day_reports_and_logs


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--rebuild-all-elections', action='store_true',
            default=False,
            help='Rebuild reports for old elections')

    def handle(self, *args, **options):
        self.stdout.write('Generating registrations reports.')
        generate_registrations_reports()
        self.stdout.write('Generating election day reports and logs.')
        generate_election_day_reports_and_logs(rebuild_all=options['rebuild_all_elections'])
        self.stdout.write('Done.')
