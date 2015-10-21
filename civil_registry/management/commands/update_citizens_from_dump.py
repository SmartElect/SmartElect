# coding: utf-8
"""
Given a SQL dump file from the CRA, update
our citizens table.
"""
import logging
from optparse import make_option
import os.path

from django.core.management.base import LabelCommand, CommandError
from django.utils.timezone import now
from civil_registry.utils import import_citizen_dump, TooManyChanges, DEFAULT_MAX_CHANGE_PERCENT

from civil_registry.models import CitizenMetadata


logger = logging.getLogger(__name__)


class Command(LabelCommand):
    args = "<filename>"
    help = "Updates civil registry data from a SQL dump"

    option_list = LabelCommand.option_list + (
        make_option(
            '--encoding',
            action='store',
            dest='encoding',
            default='UTF-8',
            help='The input file has this encoding. Default: UTF-8.'
        ),
        make_option(
            '--max-change-percent',
            action='store',
            dest='max_change_percent',
            type=float,
            default=DEFAULT_MAX_CHANGE_PERCENT,
            help='Maximum percent of existing records that can be changed. If the import '
                 'would change more than this, it will stop without changing any. This is '
                 'to guard against loss of data if a dump file is bad. It will likely need '
                 'to be overridden when initializing a nearly empty database. '
                 'Default is %f%%.' % DEFAULT_MAX_CHANGE_PERCENT
        )
    )

    def handle_label(self, label, **options):

        input_filename = label
        if not os.path.exists(input_filename):
            raise CommandError("File does not exist: %s" % input_filename)

        # Lots of output on stdout
        logging.getLogger('civil_registry').setLevel(logging.DEBUG)
        logging.getLogger('civil_registry').addHandler(logging.StreamHandler())

        logger.info("Starting at %s" % now())

        try:
            stats = import_citizen_dump(
                input_filename,
                max_change_percent=options['max_change_percent'],
                encoding=options['encoding'],
            )
        except TooManyChanges as e:
            raise CommandError(e.args[0])

        # Say what we did.
        logger.info("Records read:            %10d" % stats.records_read)
        logger.info("Unchanged records:       %10d" % stats.unchanged_count)
        logger.info("Modified records:        %10d" % stats.modified_record_count)
        logger.info("New records:             %10d" % stats.new_record_count)

        previous_total = (stats.unchanged_count + stats.modified_record_count
                          + stats.not_there_anymore_count)

        new_total = previous_total + stats.new_record_count
        logger.info("Records no longer there: %10d" % stats.not_there_anymore_count)

        logger.info("Previous total:          %10d" % previous_total)
        logger.info("New total:               %10d" % new_total)
        logger.info("Finished at:  %s" % CitizenMetadata.objects.get().dump_time)
