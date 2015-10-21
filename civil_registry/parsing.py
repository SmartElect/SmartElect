"""
Code for parsing SQL dumps from the Civil Registry.
"""
from __future__ import unicode_literals

import logging
import re

from civil_registry.forms import CitizenRecordForm


# Match rows in the sql dump. Example rows before the values row that this should match:
# INSERT INTO T_PERSONAL_DATA(PERSON_ID,NAME,FATHER_NAME_AR,GRAND_FATHER_NAME_AR,FAM_NAME,
# MOTHER_NAME_AR,GENDER,DATE_OF_BIRTH,ADDRESS,NATIONAL_ID,REGISTRY_NO,OFFICE_ID,BRANCH_ID,STATE)
# We use this regex to split the line into fields when we've counted the commas
# and realized some value has a comma so we can't just split on commas.
# Notice that it knows which fields are quoted and which aren't, and leaves
# out the quotes.  Similarly for whitespace and commas between fields.
VALUES_MATCH = re.compile(r'VALUES\('
                          " *(?P<civil_registry_id>\d*) *,"
                          " *'(?P<first_name>.*)' *,"
                          " *'(?P<father_name>.*)' *,"
                          " *'(?P<grandfather_name>.*)' *,"
                          " *'(?P<family_name>.*)' *,"
                          " *'(?P<mother_name>.*)' *,"
                          " *(?P<gender>[12]) *,"
                          " *'(?P<birth_date>.*)' *,"
                          " *'(?P<address>.*)' *,"
                          " *'(?P<national_id>.*)' *,"
                          " *'(?P<fbr_number>.*)' *,"
                          " *(?P<office_id>.*) *,"
                          " *(?P<branch_id>.*) *,"
                          " *(?P<state>.*) *\)",
                          re.UNICODE)


# These are the field names in the order we pass them
# around most places. Note that this is not the order the values
# are given to us in the input file.  Oh well.
FIELD_NAMES = ('civil_registry_id',
               'national_id', 'fbr_number', 'first_name',
               'father_name',
               'grandfather_name', 'mother_name',
               'family_name', 'gender', 'birth_date',
               'address', 'office_id', 'branch_id', 'state')


logger = logging.getLogger(__name__)


def strip_space_and_quotes(stringy):
    return stringy.strip(" '")


def match_line_re(line):
    """
    Given a string that's expected to match the VALUES_MATCH regex,
    return a tuple with the strings from the line's fields in the
    order FIELD_NAMES (see above).

    If it doesn't match, raises a ValueError.
    """
    # Note that the regex strips leading and trailing spaces and quotes
    # from the field values
    match = VALUES_MATCH.search(line)
    if match:
        return tuple(strip_space_and_quotes(match.group(f)) for f in FIELD_NAMES)
    logger.error("Line did not match regex: %r", line)
    raise ValueError("Line did not match regex: %r" % line)


def match_line_split(line):
    """
    Given a string that contains the values from a line in the
    dump, where none of the fields' values contain commas, remove
    the cruft from the beginning and end of the line and split
    the rest on commas to pick out all the fields quickly.

    Removes leading and trailing spaces and single quotes
    from the fields.

    Returns the values in FIELD_NAMES order.
    """
    # Simple split on comma, skipping "VALUES(" at the beginning
    # and ");\r\n" at the end.
    parts = line[7:-4].split(',')
    # Assign to a tuple in the order they occur on the line,
    # but at the same time, strip
    # leading and trailing whitespace and quotes:
    (civil_registry_id, first_name, father_name, grandfather_name,
     family_name, mother_name, gender,
     birth_date, address, national_id, fbr_number,
     office_id, branch_id, state) = map(strip_space_and_quotes, parts)

    # Note that we're not returning these in the same order...
    return (civil_registry_id, national_id, fbr_number,
            first_name, father_name,
            grandfather_name, mother_name,
            family_name, gender, birth_date,
            address, office_id, branch_id, state)


def break_line(line):
    """
    Given a "VALUES" line from the input, break it into
    a separate string for each field, strip off any leading
    and trailing spaces and single quotes, and return a tuple
    of the resulting strings in FIELD_NAMES order.
    """
    if line.count(',') == len(FIELD_NAMES) - 1:
        # We can just split the line on commas to get the fields
        parts = match_line_split(line)
    else:
        # Wrong number of commas - some value must have a comma in it
        # Must use the more expensive regex to split the fields
        parts = match_line_re(line)
    return parts


def line_to_dictionary(line):
    """
    Given a VALUES line from the input, return a dictionary
    with all the field values, nicely cleaned up and converted
    to the right data types.
    :param line: A VALUES line from the input
    :raises ValueError: if any inputs are not valie
    :return: a dictionary
    """
    data = dict(zip(FIELD_NAMES, break_line(line)))
    form = CitizenRecordForm(data=data)
    if not form.is_valid():
        raise ValueError(form.errors)
    return form.cleaned_data


def get_records(input_file, line_parser=line_to_dictionary):
    """
    Generator that parses the sqldump file line by line.

    Yields a stream of dictionaries with the python values
    for the Citizen table.

    :param input_file: Python file-like object to read from.
    :param line_parser: Mainly for testing. Defaults to a function that takes
      an input string and returns a dictionary with the cleaned data of a citizen record.
    """
    record = 0
    for line in input_file:
        if line.startswith('VALUES'):
            record += 1
            yield line_parser(line)
            if record % 1000000 == 0:
                logger.info('{} records read'.format(record))
        else:
            # Lines that don't start with 'VALUES' are the 'INSERT INTO (fieldnames)'
            # line and its continuation, which don't contain any actual data to import.
            pass
