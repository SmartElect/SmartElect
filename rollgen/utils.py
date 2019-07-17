# Python imports
from contextlib import contextmanager
import collections
import csv
import io
import errno
import os
import tempfile
import traceback

# Django imports
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError
from django.utils.timezone import now as django_now
from django.utils.translation import ugettext_lazy as _

# 3rd party imports
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A0, landscape
from reportlab.lib.styles import StyleSheet1, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph

# Project imports
from .constants import ROLLGEN_FLAG_FILENAME, JOB_FAILURE_FILENAME
from .strings import STRINGS
from libya_elections.constants import ARABIC_COMMA, MALE, FEMALE, UNISEX, CENTER_ID_LENGTH
from register.models import RegistrationCenter
from voting.models import Election

ASSETS_PATH = os.path.join(settings.PROJECT_ROOT, 'rollgen', 'assets')

# NAMES provide constants for lookups in the STRINGS dictionary.
GENDER_NAMES = {FEMALE: 'female', MALE: 'male', UNISEX: 'unisex'}


class JobError(Exception):
    """Base class for job-specific exceptions (but not OutOfDiskSpaceError)"""
    def __init__(self, msg):
        self.msg = msg
        super(JobError, self).__init__(msg)


class NoElectionError(JobError):
    """Raised when there's no current in-person election"""
    pass


class NoVotersError(JobError):
    """Raised when a center has no registrants (voters)"""
    pass


class NoOfficeError(JobError):
    """Raised when a center has no office (is associated with office_id NO_NAMEDTHING)"""
    pass


class OutOfDiskSpaceError(IOError):
    """Raised by out_of_disk_space_handler_context (q.v.)"""
    pass


@contextmanager
def out_of_disk_space_handler_context():
    """Context manager for code that writes to the disk. Raises OutOfDiskSpaceError if an
    out-of-disk-space condition is detected.
    """
    try:
        yield
    except (IOError, OSError) as error_instance:
        # reportlab reports out of disk space as an IOError; things like os.makedirs() report the
        # same condition as an OSError.
        if hasattr(error_instance, 'errno') and (error_instance.errno == errno.ENOSPC):
            raise OutOfDiskSpaceError("Out of disk space")
        else:
            # If it's not the specific error above, just re-raise it.
            raise


class CountingDocTemplate(SimpleDocTemplate):
    """This is an extremely simple subclass of reportlab's SimpleDocTemplate. The only extra
    feature it offers is the read-only property n_pages which reports the current number of pages
    in the document.
    """
    def __init__(self, *args, **kwargs):
        SimpleDocTemplate.__init__(self, *args, **kwargs)

        self._n_pages = 0

    @property
    def n_pages(self):
        return self._n_pages

    def handle_pageEnd(self):
        SimpleDocTemplate.handle_pageEnd(self)

        self._n_pages += 1


def read_ids(filename):
    """Read center, office, or constituency ids from a file and return them as a list of strings.

    Raises CommandError if any of them don't look like ints.

    At present this is used only by the generate_rolls management command, hence the use of
    CommandError instead of some other kind of error.
    """
    try:
        with open(filename, 'r') as f:
            lines = f.read()
    except IOError:
        raise CommandError("""I can't read the file "{}".""".format(filename))

    lines = lines.split('\n')
    lines = [line.strip() for line in lines if line.strip()]

    try:
        list(map(int, lines))
    except (ValueError, TypeError):
        raise CommandError('At least one of the ids in "{}" is not valid.'.format(filename))
    else:
        return lines


def is_iterable(an_object, include_strings=False):
    """Return True if an object is iterable, False otherwise.

    Iterable types include lists, tuples, dicts, strings, numpy arrays, etc.

    If include_strings is False, then strings are not considered iterable. This is useful because
    often we use is_iterable() to decide whether something is an object or a list of objects, and
    while one *can* loop over the contents of a string with 'for character in some_string', one
    doesn't typically want to.
    """
    try:
        iter(an_object)
        rc = True
    except TypeError:
        rc = False

    if rc and (not include_strings) and isinstance(an_object, str):
        rc = False

    return rc


def is_intable(an_object):
    """Return True if the object can be converted to an int, False otherwise."""
    intable = False
    try:
        int(an_object)
        intable = True
    except Exception:
        # Sorry for the naked except, but I don't care why the above failed.
        pass

    return intable


def is_rollgen_output_dir(dirname):
    """Given a dirname (not fully qualified), return true if it looks rollgen output, else false"""
    path = os.path.join(settings.ROLLGEN_OUTPUT_DIR, dirname, ROLLGEN_FLAG_FILENAME)
    return os.path.isfile(path)


def get_job_name(username):
    """Given a username (e.g. 'mtwain'), returns a guaranteed unique directory name"""
    # Autogenerate a directory name that includes a timestamp and the name of the current
    # user. The timestamp is microsecond-granular which guarantees directory name
    # uniqueness even if the user is 'unknown'. For example --
    #     2014-05-19.15-44-36-401151-mtwain
    return '{}-{}'.format(django_now().strftime('%Y-%m-%d.%H-%M-%S-%f'), username)


def validate_comma_delimited_ids(values, are_center_ids=False):
    """Execute quietly if every value is a potential id, else raise ValidationError.

    The input param can be a list of strings or a single comma-delimited string.

    The ids are not checked against the database.

    If are_center_ids is True, the ids are subject to an additional test specific to center ids.
    """
    if not is_iterable(values):
        values = values.split(',')

    invalid_values = []

    for value in values:
        if hasattr(value, 'strip'):
            value = value.strip()

        if (are_center_ids and (len(value) != CENTER_ID_LENGTH)) or \
           not is_intable(value):
            invalid_values.append(value)

    if invalid_values:
        invalid_values = ', '.join(invalid_values)
        raise ValidationError(_("These ids are invalid: {}").format(invalid_values))


def find_invalid_center_ids(center_ids):
    """Given a list of int center ids, return a list of those that are not in the database."""
    valid_center_ids = \
        set(RegistrationCenter.objects.filter(center_id__in=center_ids).values_list('center_id',
                                                                                    flat=True))
    return [center_id for center_id in center_ids if center_id not in valid_center_ids]


def chunker(seq, chunk_size):
    """Given a sequence, returns that sequence chunked into sublists of the given chunk_size.

    When len(seq) is evenly divisible by chunk_size, all chunks are the same size.

    When len(seq) is not evenly divisible by chunk_size, the last chunk is smaller than all the
    others.
    """
    # could be inefficient with really long lists, benchmark?
    # alternatively use itertools
    return (seq[pos:pos + chunk_size] for pos in range(0, len(seq), chunk_size))


def even_chunker(seq, n_chunks):
    """Given a sequence, returns that sequence divided into n_chunks of (roughly) the same size.
    In other words, it returns a list of lists.

    When len(seq) is evenly divisible by n_chunks, all chunks are the same size.

    When len(seq) is not evenly divisible by n_chunks, all chunks have a length within +/- 1 of
    all other chunks.

    Some examples of the length of the return chunks for len(seq) == 100:
    n_chunks ==  3: [33, 33, 34]
    n_chunks ==  5: [20, 20, 20, 20, 20]
    n_chunks ==  6: [16, 17, 17, 16, 17, 17]
    n_chunks ==  7: [14, 14, 14, 15, 14, 14, 15]
    n_chunks ==  8: [12, 13, 12, 13, 12, 13, 12, 13]
    n_chunks ==  9: [11, 11, 11, 11, 11, 11, 11, 11, 12]
    n_chunks == 15: [6, 7, 7, 6, 7, 7, 6, 7, 7, 6, 7, 7, 6, 7, 7]
    """
    length = len(seq)
    return [seq[i * length // n_chunks: (i + 1) * length // n_chunks]
            for i in range(n_chunks)]


def format_name(voter):
    """Given a register.Citizen instance, returns the voter's name formatted appropriately for
    addition to the PDFs.
    """
    fields = ['first_name', 'father_name', 'grandfather_name', 'family_name']
    # ltr here, because bidi flips output
    return ' '.join([getattr(voter, field) for field in fields])


def truncate_center_name(name):
    """Given a center name, truncates it if necessary and adds an ellipsis if truncated.
    Returns the name (truncated or otherwise).
    """
    max_len = settings.ROLLGEN_CENTER_NAME_TRUNCATE_AFTER
    if len(name) > max_len:
        name = name[:max_len] + '...'

    return name


def build_copy_info(center):
    """Given a RegistrationCenter instance, returns a string containing copy info (may be blank).

    The returned string is meant to be inserted directly into a cover page.

    Copy info is blank in most cases.

    For centers that are copies, the string contains STRINGS['copy_of'] along with the center_id
    of the original center.

    For centers that have copies, the string contains the appropriate STRINGS entry
    (copied_by_singular or copied_by_plural) along with a list of the centers that copy this one.
    """
    copied_by = list(center.copied_by.all())
    if center.copy_of:
        copy_info = '%s: %s' % (STRINGS['copy_of'], center.copy_of.center_id)
    elif copied_by:
        strings_key = 'copied_by_singular' if (len(copied_by) == 1) else 'copied_by_plural'
        copied_by = [copy_center.center_id for copy_center in copied_by]
        copied_by = (ARABIC_COMMA + ' ').join(map(str, copied_by))
        copy_info = '%s: %s' % (STRINGS[strings_key], copied_by)
    else:
        copy_info = ''

    return copy_info


def handle_job_exception(exception, output_path):
    """Given an exception raised by generate_rolls(), writes it to the fail file in output_path."""
    if isinstance(exception, (NoOfficeError, NoVotersError)):
        fail_message = exception.msg
        is_expected = True
    elif isinstance(exception, OutOfDiskSpaceError):
        fail_message = 'Out of disk space. Stack trace follows.\n\n'
        fail_message += traceback.format_exc()
        is_expected = True
    else:
        # Catch all
        fail_message = 'Execution failed with the following error:\n'
        fail_message += str(exception)
        fail_message += '\nStack trace follows.\n\n'
        fail_message += traceback.format_exc()
        is_expected = False

    with open(os.path.join(output_path, JOB_FAILURE_FILENAME), 'wb') as f:
        f.write(fail_message.encode('utf-8'))

    return is_expected


def find_longest_string_in_list(the_strings):
    """Given a list of strings, return the longest (widest) as rendered in a PDF.

    This measures the width of strings on the printed page in the Arabic font that rollgen uses.
    It does not simply count characters.

    This function has two limitations.

    First, if a string is long enough to wrap onto multiple lines, this function won't be able
    to figure out which string is which. When this code detects that a string has been wrapped,
    it simply gives up and raises a ValueError. In practice a string needs to be over 30" long
    printed in a 10 point font for wrapping to occur. This is ~600 characters. As of Nov. 2014, the
    longest center/subcon name is 79 characters.

    The second limitation is that even very long strings won't wrap if they contain no spaces or
    punctuation (e.g. 'abc' * 500). Reportlab prints a string like that right off the end of the
    page, so this code can't determine its true length and may return an incorrect result.

    In practice this code should not encounter strings >= 600 characters containing no spaces.
    """
    fh, filename = tempfile.mkstemp()
    os.close(fh)

    stylesheet = StyleSheet1()
    # The style uses a small font to minimize the odds that a string will wrap to a second line.
    # I also set the left/right indent to 0.
    stylesheet.add(ParagraphStyle(name='Arabic',
                                  fontName='Arabic',
                                  wordWrap='RTL',
                                  alignment=TA_RIGHT,
                                  fontSize=10,
                                  leading=10,
                                  spaceAfter=5,
                                  firstLineIndent=0,
                                  rightIndent=0))

    # Landscape orientation, a large paper size, and generous left/right margins reduce the odds
    # that a string will wrap.
    doc = CountingDocTemplate(filename, pagesize=landscape(A0), leftMargin=.25 * cm,
                              rightMargin=.25 * cm, topMargin=1 * cm, bottomMargin=1 * cm)

    # I map each string to its own Paragraph.
    strings_to_paragraphs = collections.OrderedDict()
    for item in the_strings:
        strings_to_paragraphs[item] = Paragraph(item, stylesheet['Arabic'])

    doc.build(list(strings_to_paragraphs.values()))

    os.remove(filename)

    longest = ('', 0)
    for the_string, the_paragraph in strings_to_paragraphs.items():
        line_lengths = the_paragraph.getActualLineWidths0()
        n_line_lengths = len(line_lengths)

        if n_line_lengths == 0:
            # Reportlab doesn't like to construct paragraphs out of empty strings and strings
            # that contain only spaces. It refuses to emit a line at all in the PDF. In that case,
            # getActualLineWidths0() returns an empty list.
            string_length = 0
        elif n_line_lengths == 1:
            # This is the expected case
            string_length = line_lengths[0]
        else:
            # ==> n_line_lengths > 1, which means a line has wrapped
            msg = "The following string is too long for this function's limitations:\n"
            msg += the_string
            raise ValueError(msg)

        if string_length > longest[1]:
            # A new champion!
            longest = (the_string, string_length)

    return longest[0]


def generate_polling_metadata_csv():
    election = Election.objects.get_most_current_election()

    from rollgen.models import Station

    stations = Station.objects.filter(election=election)

    header = ('Centre #',
              'Centre Name',
              'Centre Type',
              'Office #',
              'Constituency #',
              'Constituency Name',
              'SubConstituency #',
              'SubConstituency Name',
              'Station number',
              'Station Gender',
              'Number of Registrants',
              'First Name',
              'First Name Number',
              'Last Name',
              'Last Name Number',
              'When Generated',
              )

    rows = [header]
    for station in stations:
        center = station.center
        rows.append((str(center.center_id),
                     center.name,
                     RegistrationCenter.Types.NAMES['ar'][center.center_type],
                     str(center.office.id),
                     str(center.constituency.id),
                     center.constituency.name_arabic,
                     str(center.subconstituency.id),
                     center.subconstituency.name_arabic,
                     str(station.number),
                     GENDER_NAMES[station.gender],
                     str(station.n_registrants),
                     station.first_voter_name,
                     str(station.first_voter_number),
                     station.last_voter_name,
                     str(station.last_voter_number),
                     station.creation_date.strftime('%Y-%m-%d %H:%M:%S')
                     ))

    faux_file = io.StringIO()
    writer = csv.writer(faux_file)
    writer.writerows(rows)
    return faux_file.getvalue().encode()
