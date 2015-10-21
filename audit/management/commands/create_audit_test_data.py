# Python imports
from optparse import make_option

# 3rd party imports
from django.core.management import BaseCommand

# Project imports
from audit.tests.create_test_data import create, DELETE_EXISTING_DATA_ARG


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option(DELETE_EXISTING_DATA_ARG,
                    action='store_const',
                    const=True,
                    default=False,
                    help='Remove existing data first'),
    )

    args = ''
    help = 'Creates audit test data'

    def handle(self, *args, **options):
        return create(delete_old_data=options['yes_delete_my_data'])
