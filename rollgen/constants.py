# Python imports
from __future__ import division
from __future__ import unicode_literals

# Django imports


# METADATA_FILENAME is the file to which generate_rolls() writes job metadata
METADATA_FILENAME = 'job_metadata.json'
# JOB_FAILURE_FILENAME is the file to which the Celery task writes failure info if an exception
# occurs while running or attempting to run generate_rolls().
JOB_FAILURE_FILENAME = 'failure_info.txt'
# ROLLGEN_FLAG_FILENAME is the file written immediately to every rollgen directory on creation of
# a Job instance. It enables the Web views to identify rollgen directories easily.
ROLLGEN_FLAG_FILENAME = 'this_is_a_rollgen_job.txt'
ROLLGEN_FLAG_FILENAME_CONTENT = \
    "This file identifies this directory as rollgen output. It has no other purpose."

# Job name must be at least one character long, may not start with a dot, and may not contain
# backslash nor forward slash in any position.
JOB_NAME_REGEX = r"""(?P<dirname>[^./\\]{1}[^/\\]*)"""
OFFICE_ID_REGEX = r"""(?P<office_id>\d{1,4})"""
ZIP_FILENAME_REGEX = OFFICE_ID_REGEX + '[.]zip'
PDF_FILENAME_REGEX = r"""(?P<filename>.*[.]pdf)"""

# People (voters) are sorted by name. Note that database sort order for these Arabic fields can
# differ from the Python sort order, so be consistent about using the database for sorting.
# ref: https://github.com/hnec-vr/libya-elections/issues/1221
CITIZEN_SORT_FIELDS = ('first_name', 'father_name', 'grandfather_name', 'family_name', )
