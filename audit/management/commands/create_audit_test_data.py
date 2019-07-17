# 3rd party imports
from django.core.management import BaseCommand

# Project imports
from audit.tests.create_test_data import create, DELETE_EXISTING_DATA_ARG


class Command(BaseCommand):
    args = ''
    help = 'Creates audit test data'

    def add_arguments(self, parser):
        parser.add_argument(DELETE_EXISTING_DATA_ARG,
                            action='store_true',
                            default=False,
                            help='Remove existing data first')

    def handle(self, *args, **options):
        return create(delete_old_data=options['yes_delete_my_data'])
