# Python imports
from __future__ import unicode_literals
from __future__ import division
import logging
from optparse import make_option

# 3rd party imports


# Django imports
from django.core.management.base import BaseCommand, CommandError

# Project imports
from register.models import RegistrationCenter, SubConstituency
from rollgen.arabic_reshaper import reshape
from rollgen.utils import find_longest_string_in_list

logger = logging.getLogger('rollgen')

stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
logger.addHandler(stream_handler)


class Command(BaseCommand):
    """Django mgmt command for finding the longest center or subcon name in the DB.

    It uses parts of rollgen to find the longest subcon or center name (depending on the
    entity argument) and writes that name to a file.

    This is not super useful on its own, but it's a critical part of
    rollgen_longest_strings_test.sh. Read the comment in that file for more information.
    """
    args = '<entity>'

    option_list = BaseCommand.option_list + (
        make_option('--filename',
                    action='store',
                    dest='filename',
                    default=None,
                    help='The longest string will be written to this file (defaults to stdout)'),
        )

    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError('Please specify either centers or subconstituencies.')

        entity = args[0].lower()
        valid_entities = ('centers', 'subconstituencies')
        if entity not in valid_entities:
            raise CommandError('Entity must be either centers or subconstituencies.')

        if entity == 'centers':
            centers = RegistrationCenter.objects.all()

            longest_name = find_longest_string_in_list([reshape(center.name) for center in centers])
        else:
            subconstituencies = SubConstituency.objects.all()

            longest_name = find_longest_string_in_list([reshape(subconstituency.name_arabic) for
                                                       subconstituency in subconstituencies])

        if options['filename']:
            open(options['filename'], 'wb').write(longest_name.encode('utf-8'))
        else:
            self.stdout.write(longest_name)
