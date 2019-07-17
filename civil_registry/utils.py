import codecs
import logging
import string

from django.db import transaction
from django.utils import six
from django.utils.timezone import now

from civil_registry.models import TempCitizen, Citizen, CitizenMetadata
from civil_registry.parsing import get_records
from libya_elections.constants import NID_LENGTH, MIN_NATIONAL_ID, MAX_NATIONAL_ID
from libya_elections.db_mirror import mirror_database
from libya_elections.db_utils import delete_all, BatchOperations

DEFAULT_MAX_CHANGE_PERCENT = 0.5


logger = logging.getLogger(__name__)


class TooManyChanges(Exception):
    pass


def import_citizen_dump(input_filename,
                        max_change_percent=DEFAULT_MAX_CHANGE_PERCENT,
                        encoding='UTF-8'):

    with transaction.atomic():

        # Clear out TempCitizen table. (We clear it at the end too, but this makes
        # extra sure that we start with it empty.)
        delete_all('default', [TempCitizen])

        num_records_at_start = Citizen.objects.count()

        #
        # 1. Fill our temp table with the data from the latest dump
        #
        logger.info("Loading data from dump")
        input_file = codecs.open(input_filename, encoding=encoding)
        logger.info("Reading %s" % input_filename)
        batch = BatchOperations(TempCitizen)
        records_read = 0
        for record in get_records(input_file):
            records_read += 1
            batch.add(record)
        batch.flush()

        #
        # 2. Sync data from temp table to our real table
        #
        logger.info("Updating our own database")
        stats = mirror_database(from_model=TempCitizen,
                                to_model=Citizen)

        # See what % of the records we're changing
        if num_records_at_start > 0:
            num_changes = (stats.modified_record_count + stats.new_record_count
                           + stats.not_there_anymore_count)
            percent_changed = 100 * (num_changes / num_records_at_start)
            if percent_changed > max_change_percent:
                raise TooManyChanges(
                    "Too many changes, aborting Citizen data import. Max change is %f%% but "
                    "the import would have changed %f%% records (%d/%d).  Use "
                    "--max-change-percent=NN to override this limit if necessary."
                    % (max_change_percent, percent_changed, num_changes, num_records_at_start))

        # Add our data
        stats.records_read = records_read

        # Make a note of when we did it
        timestamp = now()
        CitizenMetadata.objects.update_or_create(defaults=dict(dump_time=timestamp))

        # Flag any records that turned up missing
        if stats.missing_pks:
            Citizen.objects.filter(pk__in=stats.missing_pks, missing=None).update(missing=timestamp)

        # And we're done!

        # Clear out our temp table (no point in taking up disk space)
        delete_all('default', [TempCitizen])

    return stats


def get_citizen_by_national_id(national_id):
    """
    Return Citizen with the given national_id, or else None.  Missing
    Citizens are not considered.

    Note that the object manager for Citizen will ignore missing citizens,
    so we don't need to explicitly filter those out.
    """
    return Citizen.objects.filter(national_id=national_id).first()


def is_valid_national_id(national_id):
    """
    Given a national ID in string or integer form, return True if it's a syntactically
    valid ID - 12 digits, first digits 1 or 2.
    """
    if isinstance(national_id, six.string_types):
        if not national_id.isdigit():
            return False
        if NID_LENGTH != len(national_id):
            return False
        national_id = int(national_id)
    return MIN_NATIONAL_ID <= national_id <= MAX_NATIONAL_ID


def is_valid_person_id(person_id):
    """
    Given a person ID in string or integer form, return True if it's a syntactically
    valid ID - all numeric
    """
    if isinstance(person_id, six.string_types):
        return person_id.isdigit()
    return True


def is_valid_fbr_number(fbr_number):
    """
    Given a fbr_number in string or integer form, return True if it's syntactically valid. Either
    all numeric or a string of alphabetic characters followed by a string of integers.
    """
    if isinstance(fbr_number, six.string_types):
        return fbr_number.lstrip(string.ascii_letters).isdigit()
    return True
