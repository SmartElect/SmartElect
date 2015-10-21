from optparse import make_option

from django.core.management import BaseCommand
from reporting_api.reports import generate_registrations_reports, \
    generate_election_day_reports_and_logs


class Command(BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option('--rebuild-all-elections', action='store_const', const=True,
                    default=False,
                    help='Rebuild reports for old elections'),
    )

    def handle(self, *args, **options):
        self.stdout.write('Generating registrations reports.')
        generate_registrations_reports()
        self.stdout.write('Generating election day reports and logs.')
        generate_election_day_reports_and_logs(rebuild_all=options['rebuild_all_elections'])
        self.stdout.write('Done.')
