# -*- coding: utf-8 -*-
# Python imports
from __future__ import unicode_literals
import errno
import os
import shutil
import tempfile

# Django imports
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError
from django.conf import settings
from django.test import TestCase

# Project imports
from .factories import create_voters
from ..arabic_reshaper import reshape
from ..constants import JOB_FAILURE_FILENAME
from ..generate_pdf_ed import station_name_range
from ..models import station_distributor
from ..strings import normalize_newlines, STRINGS
from ..utils import chunker, format_name, build_copy_info, is_iterable, GENDER_NAMES, \
    OutOfDiskSpaceError, out_of_disk_space_handler_context, validate_comma_delimited_ids, \
    find_invalid_center_ids, read_ids, handle_job_exception, NoVotersError, NoOfficeError, \
    find_longest_string_in_list, even_chunker
from libya_elections.constants import ARABIC_COMMA, CENTER_ID_LENGTH, MALE, FEMALE, UNISEX
from register.tests.factories import RegistrationCenterFactory


class TestUtilsMisc(TestCase):
    """Test miscellaneous utils functions that need no special setup"""

    def check_no_loss(self, original, chunked):
        """Given a flat list and the same list chunked (a list of lists), checks to see that each
        item in the chunked list appears the same number of times and in the same place as in
        the original."""
        # Flatten the chunked list
        chunked = [item for sublist in chunked for item in sublist]
        self.assertSequenceEqual(original, chunked)

    def check_same_size(self, chunked):
        """Given a list of lists, checks to see that each sublist is the same size as its peers."""
        expected_size = len(chunked[0])
        self.assertTrue(all([len(chunk) == expected_size for chunk in chunked]))

    def check_similar_size(self, chunked):
        """Given a list of lists, checks to see that the length of each sublist is no more
        than +/-1 from its peers."""

        lengths = [len(chunk) for chunk in chunked]
        # There should be 1 or 2 distinct lengths.
        self.assertLessEqual(len(set(lengths)), 2)

        # The difference between the min & max should be 0 or 1.
        self.assertLessEqual(max(lengths) - min(lengths), 1)

    def test_normalize_newlines(self):
        """tests utils.normalize_newlines()"""
        self.assertEqual(normalize_newlines('\r\n'), '\n')
        self.assertEqual(normalize_newlines('\n\r'), '\n' * 2)
        self.assertEqual(normalize_newlines('\r\r'), '\n' * 2)
        self.assertEqual(normalize_newlines('\n\r\n'), '\n' * 2)
        self.assertEqual(normalize_newlines('\r\r\n\r'), '\n' * 3)
        self.assertEqual(normalize_newlines('\n\r\r\n'), '\n' * 3)
        self.assertEqual(normalize_newlines('\n\n\n'), '\n' * 3)
        self.assertEqual(normalize_newlines('\r\r\r'), '\n' * 3)
        self.assertEqual(normalize_newlines('\r\n\r\n'), '\n' * 2)
        self.assertEqual(normalize_newlines('\r\n\r\r\n'), '\n' * 3)
        self.assertEqual(normalize_newlines('\r\n\n\r\n'), '\n' * 3)

    def test_chunker(self):
        """tests utils.chunker()"""
        data = range(100)

        # Test chunking w/evenly-sized chunks
        chunked = list(chunker(data, 5))
        self.assertEqual(len(chunked), 20)

        self.check_same_size(chunked)
        self.check_no_loss(data, chunked)

        # Test chunking w/evenly-sized chunks
        chunked = list(chunker(data, 2))
        self.assertEqual(len(chunked), 50)

        self.check_same_size(chunked)
        self.check_no_loss(data, chunked)

        # Test chunking w/small chunks that are not all the same size
        chunked = list(chunker(data, 3))
        self.assertEqual(len(chunked), 34)

        self.check_same_size(chunked[:-1])
        self.assertTrue(len(chunked[-1]) == 1)
        self.check_no_loss(data, chunked)

        # Test chunking w/large chunks that are not all the same size
        chunked = list(chunker(data, 40))
        self.assertEqual(len(chunked), 3)

        self.check_same_size(chunked[:-1])
        self.assertTrue(len(chunked[0]) == 40)
        self.assertTrue(len(chunked[2]) == 20)
        self.check_no_loss(data, chunked)

        # Test pathological case where each chunk has len() == 1
        chunked = list(chunker(data, 1))
        self.assertEqual(len(chunked), len(data))

        self.check_same_size(chunked)
        self.check_no_loss(data, chunked)

        # Test pathological case where there's only one chunk
        chunked = list(chunker(data, len(data)))
        self.assertEqual(len(chunked), 1)

        self.check_same_size(chunked)
        self.check_no_loss(data, chunked)

    def test_even_chunker(self):
        """tests utils.even_chunker()"""
        data = range(100)

        # Test chunking w/same-sized chunks
        chunked = even_chunker(data, 5)
        self.assertEqual(len(chunked), 5)
        self.assertEqual(len(chunked[0]), len(data) / 5)

        self.check_same_size(chunked)
        self.check_no_loss(data, chunked)

        # Test chunking w/same-sized chunks
        chunked = even_chunker(data, 20)
        self.assertEqual(len(chunked), 20)

        self.check_same_size(chunked)
        self.check_no_loss(data, chunked)

        # Test chunking w/large chunks that are not all the same size
        chunked = list(even_chunker(data, 3))
        self.assertEqual(len(chunked), 3)

        self.check_similar_size(chunked)
        self.check_no_loss(data, chunked)

        # Test chunking w/small chunks that are not all the same size
        chunked = list(even_chunker(data, 33))
        self.assertEqual(len(chunked), 33)

        self.check_similar_size(chunked)
        self.check_no_loss(data, chunked)

        # Test chunking w/chunks that are not all the same size
        chunked = list(even_chunker(data, 13))
        self.assertEqual(len(chunked), 13)

        self.check_similar_size(chunked)
        self.check_no_loss(data, chunked)

        # Test pathological case where each chunk has len() == 1
        chunked = list(even_chunker(data, len(data)))
        self.assertEqual(len(chunked), len(data))
        self.assertEqual(len(chunked[0]), 1)

        self.check_same_size(chunked)
        self.check_no_loss(data, chunked)

        # Test pathological case where there's only one chunk w/len() == 100
        chunked = list(even_chunker(data, 1))
        self.assertEqual(len(chunked), 1)
        self.assertEqual(len(chunked[0]), 100)

        self.check_same_size(chunked)
        self.check_no_loss(data, chunked)

    def test_gender_strings(self):
        """tests to see that the Arabic words for male/female/unisex are associated with the
        correct constants.
        """
        # Note that the strings in STRINGS have already been through the Arabic reshaper.
        self.assertEqual(STRINGS['male'], reshape("ذكر"))
        self.assertEqual(STRINGS[GENDER_NAMES[MALE]], STRINGS['male'])

        self.assertEqual(STRINGS['female'], reshape("أنثى"))
        self.assertEqual(STRINGS[GENDER_NAMES[FEMALE]], STRINGS['female'])

        self.assertEqual(STRINGS['unisex'], reshape("ذكر + أنثى"))
        self.assertEqual(STRINGS[GENDER_NAMES[UNISEX]], STRINGS['unisex'])

    def test_out_of_disk_space_handler_context(self):
        """exercises utils.out_of_disk_space_handler_context"""

        # test that most exception types are re-raised untouched.
        with self.assertRaises(ValueError):
            with out_of_disk_space_handler_context():
                raise ValueError

        with self.assertRaises(TypeError):
            with out_of_disk_space_handler_context():
                raise TypeError

        # Ensure that OSErrors and IOErrors that don't meet the specified criteria are not
        # translated into OutOfDiskSpaceError.
        with self.assertRaises(OSError):
            with out_of_disk_space_handler_context():
                raise OSError

        with self.assertRaises(IOError):
            with out_of_disk_space_handler_context():
                raise IOError

        with self.assertRaises(OSError):
            with out_of_disk_space_handler_context():
                exception = OSError()
                exception.errno = errno.EOVERFLOW
                raise exception

        with self.assertRaises(IOError):
            with out_of_disk_space_handler_context():
                exception = IOError()
                exception.errno = errno.ECONNRESET
                raise exception

        # test that errors of the right kind are translated into OutOfDiskSpaceError.
        with self.assertRaises(OutOfDiskSpaceError):
            with out_of_disk_space_handler_context():
                exception = OSError()
                exception.errno = errno.ENOSPC
                raise exception

        with self.assertRaises(OutOfDiskSpaceError):
            with out_of_disk_space_handler_context():
                exception = IOError()
                exception.errno = errno.ENOSPC
                raise exception

    def test_is_iterable(self):
        """exercises utils_for_tests.is_iterable()"""
        self.assertFalse(is_iterable(42))
        self.assertFalse(is_iterable(object()))
        self.assertTrue(is_iterable([]))
        self.assertTrue(is_iterable(range(5)))
        self.assertTrue(is_iterable({}))
        self.assertTrue(is_iterable(tuple()))
        self.assertTrue(is_iterable('foo', True))
        self.assertFalse(is_iterable('foo', False))
        self.assertFalse(is_iterable('foo'))

    def test_validate_comma_delimited_ids_list_of_strings(self):
        """exercises validate_comma_delimited_ids with a list of strings param"""
        ids = ['1', '3', '7']
        validate_comma_delimited_ids(ids)

        # Raises no error

    def test_validate_comma_delimited_ids_comma_delimited_string(self):
        """exercises validate_comma_delimited_ids with a string of comma delimited ids"""
        ids = ','.join(['1', '3', '7'])
        validate_comma_delimited_ids(ids)

        # Raises no error

    def test_validate_comma_delimited_ids_non_int_center_id(self):
        """ensure validate_comma_delimited_ids rejects a non-int id"""
        ids = ','.join(['1', '3', '7'])
        ids += ',abcd'
        with self.assertRaises(ValidationError):
            validate_comma_delimited_ids(ids)

    def test_validate_comma_delimited_ids_center_id_too_long(self):
        """ensure validate_comma_delimited_ids rejects an overly long center id"""
        center_ids = ','.join([char * CENTER_ID_LENGTH for char in ('1', '3', '7')])
        center_ids += (',' + '9' * (CENTER_ID_LENGTH + 1))

        with self.assertRaises(ValidationError):
            validate_comma_delimited_ids(center_ids, True)

    def test_find_invalid_center_ids(self):
        """exercise find_invalid_center_ids()"""
        centers = [RegistrationCenterFactory(), RegistrationCenterFactory()]
        center_ids = [center.center_id for center in centers]
        center_ids += [99999, 88888]

        # Note that order is preserved
        self.assertEqual([99999, 88888], find_invalid_center_ids(center_ids))

    def test_find_longest_string_in_list_english(self):
        """exercise find_longest_string_in_list() with simple English strings"""
        # be sure to test with a blank string which forces find_longest_string_in_list() to do
        # some special handling
        strings = ('', 'iiiii', 'WWW')
        longest = strings[2]

        # find_longest_string_in_list() returns the index of the widest string
        self.assertEqual(find_longest_string_in_list(strings), longest)

    def test_find_longest_string_in_list_arabic(self):
        """exercise find_longest_string_in_list() with Arabic strings"""
        strings = ('', reshape(u'\ufe9a'), reshape('\ufe8d' * 3))
        longest = strings[1]
        self.assertEqual(find_longest_string_in_list(strings), longest)

        strings = (u'\u0637\u0628\u0631\u0642',
                   u'\u0627\u0644\u0642\u0628\u0629',
                   u'\u062f\u0631\u0646\u0629',
                   u'\u0634\u062d\u0627\u062a',
                   u'\u0627\u0644\u0628\u064a\u0636\u0627\u0621',
                   u'\u0627\u0644\u0645\u0631\u062c',
                   u'\u0642\u0635\u0631 \u0644\u064a\u0628\u064a\u0627',
                   u'\u0628\u0646\u063a\u0627\u0632\u064a',
                   u'\u062a\u0648\u0643\u0631\u0627',
                   u'\u0627\u0644\u0627\u0628\u064a\u0627\u0631',
                   u'\u0642\u0645\u064a\u0646\u0633',
                   u'\u0633\u0644\u0648\u0642',
                   u'\u0627\u062c\u062f\u0627\u0628\u064a\u0627',
                   u'\u0627\u0644\u0628\u0631\u064a\u0642\u0629',
                   u'\u0623\u0648\u062c\u0644\u0629',
                   u'\u062c\u0627\u0644\u0648 - \u062c\u062e\u0631\u0629',
                   u'\u062a\u0627\u0632\u0631\u0628\u0648\u0627',
                   u'\u0627\u0644\u0643\u0641\u0631\u0629',
                   u'\u0627\u0644\u0633\u062f\u0631\u0629',
                   u'\u0633\u0631\u062a',
                   u'\u0627\u0644\u062c\u0641\u0631\u0629',
                   u'\u0633\u0628\u0647\u0627',
                   u'\u0627\u0644\u0634\u0627\u0637\u0626',
                   u'\u0627\u0648\u0628\u0627\u0631\u064a',
                   u'\u063a\u0627\u062a',
                   u'\u0648\u0627\u062f\u064a \u0639\u062a\u0628\u0629',
                   )
        strings = [reshape(s) for s in strings]
        longest = strings[15]
        self.assertEqual(find_longest_string_in_list(strings), longest)

    def test_find_longest_string_in_list_force_error(self):
        """test that find_longest_string_in_list() raises an error when a string wraps"""
        strings = ('a', 'b', 'c ' * 800)

        with self.assertRaises(ValueError):
            find_longest_string_in_list(strings)


class TestReadIds(TestCase):
    """Exercise read_ids()"""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir)

    def get_temp_file(self):
        """Return a file object for a temp file that will be automatically cleaned up"""
        f, filename = tempfile.mkstemp(dir=self.temp_dir)
        os.close(f)
        self.filename = filename
        return open(filename, 'w')

    def test_read_ids_positive_case(self):
        """ensure read_ids() works"""
        with self.get_temp_file() as f:
            f.write("\n42\n77777\n\t12  \n  77\n88\n\n\n\n")

        self.assertEqual(read_ids(self.filename), ['42', '77777', '12', '77', '88'])

    def test_read_ids_bad_filename(self):
        """ensure read_ids() fails predictably on a non-existent file"""
        with self.assertRaises(CommandError):
            read_ids('there_is_no_file_with_this_name')

    def test_read_ids_bad_content(self):
        """ensure read_ids() fails predictably on a file with bad content"""
        with self.get_temp_file() as f:
            f.write("\n42\n77777\n\t12  \n  77\n88\n\n\n\nisafakjsflsdhfjkdh\n")

        with self.assertRaises(CommandError):
            read_ids(self.filename)


class TestHandleJobException(TestCase):
    """Exercise handle_job_exception()"""

    @classmethod
    def setUpClass(cls):
        cls.output_path = tempfile.mkdtemp()
        cls.expected_filename = os.path.join(cls.output_path, JOB_FAILURE_FILENAME)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.output_path)

    def test_no_voters_exception(self):
        """Exercise handle_job_exception() w/a NoVotersError"""
        exception_instance = NoVotersError('this is a test')
        self.assertTrue(handle_job_exception(exception_instance, self.output_path))
        self.assertTrue(os.path.exists(self.expected_filename))

        with open(self.expected_filename, 'rb') as f:
            content = f.read().decode('utf-8')
        self.assertEqual('this is a test', content)

    def test_no_office_exception(self):
        """Exercise handle_job_exception() w/a NoOfficeError"""
        exception_instance = NoOfficeError('this is a test')
        self.assertTrue(handle_job_exception(exception_instance, self.output_path))
        self.assertTrue(os.path.exists(self.expected_filename))

        with open(self.expected_filename, 'rb') as f:
            content = f.read().decode('utf-8')
        self.assertEqual('this is a test', content)

    def test_out_of_disk_space_exception(self):
        """Exercise handle_job_exception() w/an OutOfDiskSpaceError"""
        exception_instance = OutOfDiskSpaceError('this is a test')
        self.assertTrue(handle_job_exception(exception_instance, self.output_path))
        self.assertTrue(os.path.exists(self.expected_filename))

        with open(self.expected_filename, 'rb') as f:
            content = f.read().decode('utf-8')
        self.assertIn('Out of disk space. Stack trace follows.', content)
        self.assertGreater(len(content), len('Out of disk space. Stack trace follows.'))

    def test_unanticipated_exception(self):
        """Exercise handle_job_exception() w/a miscellaneous exception"""
        exception_instance = ValueError('no one inquisits the spanish exception!')
        self.assertFalse(handle_job_exception(exception_instance, self.output_path))
        self.assertTrue(os.path.exists(self.expected_filename))

        with open(self.expected_filename, 'rb') as f:
            content = f.read().decode('utf-8')
        self.assertIn('no one inquisits the spanish exception!', content)
        self.assertIn('Stack trace follows', content)


class TestBuildCopyInfo(TestCase):
    """Exercise utils.build_copy_info()"""
    def test_no_copy(self):
        """Exercise build_copy_info() for a center with no copy stuff"""
        center = RegistrationCenterFactory()
        self.assertEqual(build_copy_info(center), '')

    def test_copy_of(self):
        """Exercise build_copy_info() for a center that is a copy"""
        original = RegistrationCenterFactory()
        copy_center = RegistrationCenterFactory(copy_of=original)
        expected = '{}: {}'.format(STRINGS['copy_of'], copy_center.copy_of.center_id)
        self.assertEqual(build_copy_info(copy_center), expected)

    def test_copied_by_one(self):
        """Exercise build_copy_info() for a center that has a single copy"""
        original = RegistrationCenterFactory()
        RegistrationCenterFactory(copy_of=original)
        expected = '{}: {}'.format(STRINGS['copied_by_singular'],
                                   original.copied_by.all()[0].center_id)
        self.assertEqual(build_copy_info(original), expected)

    def test_copied_by_multiple(self):
        """Exercise build_copy_info() for a center that has multiple copies"""
        original = RegistrationCenterFactory()
        copy_centers = RegistrationCenterFactory.create_batch(3, copy_of=original)
        copy_center_ids = sorted([center.center_id for center in copy_centers])
        copy_center_ids = (ARABIC_COMMA + ' ').join(map(str, copy_center_ids))
        expected = '{}: {}'.format(STRINGS['copied_by_plural'], copy_center_ids)
        self.assertEqual(build_copy_info(original), expected)


class TestStationNameRange(TestCase):
    """Exercise utils.station_name_range()."""
    def test_male_station(self):
        """exercise station_name_range with a male station"""
        voter_roll = create_voters(5, MALE)

        station = station_distributor(voter_roll)[0]

        first_voter = voter_roll[0]
        last_voter = voter_roll[-1]
        expected = [[reshape(format_name(first_voter)), str(first_voter.registrant_number),
                     STRINGS['first']],
                    [reshape(format_name(last_voter)), str(last_voter.registrant_number),
                     STRINGS['last']]
                    ]

        actual = station_name_range(station)

        self.assertListEqual(expected, actual)

    def test_female_station(self):
        """exercise station_name_range with a female station"""
        voter_roll = create_voters(5, FEMALE)

        station = station_distributor(voter_roll)[0]

        first_voter = voter_roll[0]
        last_voter = voter_roll[-1]
        expected = [[reshape(format_name(first_voter)), str(first_voter.registrant_number),
                     STRINGS['first']],
                    [reshape(format_name(last_voter)), str(last_voter.registrant_number),
                     STRINGS['last']]
                    ]

        actual = station_name_range(station)

        self.assertListEqual(expected, actual)

    def test_unisex_station(self):
        """exercise station_name_range with a unisex station"""
        n_voters = (settings.ROLLGEN_UNISEX_TRIGGER - 1) * 2
        voter_roll = create_voters(n_voters)

        males = [voter for voter in voter_roll if voter.gender == MALE]
        females = [voter for voter in voter_roll if voter.gender == FEMALE]

        voter_roll = males + females

        station = station_distributor(voter_roll)[0]

        first_voter_m = males[0]
        last_voter_m = males[-1]
        first_voter_f = females[0]
        last_voter_f = females[-1]

        template = '{} ' + STRINGS['first']
        expected = [[reshape(format_name(first_voter_m)), str(first_voter_m.registrant_number),
                     template.format(STRINGS['male'])],
                    [reshape(format_name(last_voter_m)), str(last_voter_m.registrant_number),
                     STRINGS['last']],
                    [],
                    [reshape(format_name(first_voter_f)), str(first_voter_f.registrant_number),
                     template.format(STRINGS['female'])],
                    [reshape(format_name(last_voter_f)), str(last_voter_f.registrant_number),
                     STRINGS['last']]
                    ]

        actual = station_name_range(station)

        self.assertListEqual(expected, actual)

    def test_nonsense_station(self):
        """test that station_name_range() with an invalid gender raises an error"""
        voter_roll = create_voters(1, FEMALE)

        # Create a known-bad gender
        bogus_gender = 0
        while bogus_gender in (FEMALE, MALE, UNISEX):
            bogus_gender += 1

        station = station_distributor(voter_roll)[0]
        station.gender = bogus_gender
        for voter in voter_roll:
            voter.gender = bogus_gender

        with self.assertRaises(ValueError):
            station_name_range(station)
