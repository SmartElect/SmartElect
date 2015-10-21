# Python imports
from __future__ import unicode_literals
from __future__ import division

# 3rd party imports
from bidi.algorithm import get_display as apply_bidi

# Django imports
from django.conf import settings

# Project imports
from .factories import create_voters, generate_arabic_place_name
from .base import TestGeneratePdfBase
from .utils_for_tests import NBSP, extract_pdf_page, extract_textlines, clean_textlines, \
    unwrap_lines
from ..arabic_reshaper import reshape
from ..generate_pdf_ed import generate_pdf_station_sign, generate_pdf_station_book, \
    generate_pdf_center_list, station_name_range
from ..utils import truncate_center_name, format_name
from libya_elections.constants import ARABIC_COMMA, MALE, FEMALE, UNISEX
from register.tests.factories import RegistrationCenterFactory


def format_station_name_range_lines(lines):
    """Given a list of lines from station_name_range(), format them as expected output"""
    # station_name_range() returns a list of lists; the inner lists each have 3 items and
    # consist of [voter name, voter number, 'first' or 'last' (in Arabic)].
    formatted = []
    for line in lines:
        if line:
            name, number, first_or_last = line
            formatted.append(apply_bidi(name) + str(number) + apply_bidi(first_or_last))

    return formatted


class TestGeneratePdfEdPageCounts(TestGeneratePdfBase):
    """Exercises generate_pdf_ed.py with regard to page counts"""
    def test_generate_pdf_station_book_unisex(self):
        """test generating a station book for a unisex station"""
        # The # of males and females must be < UNISEX_TRIGGER and also not an even multiple
        # of settings.ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_BOOK (to trigger full test coverage).
        n_males = n_females = settings.ROLLGEN_UNISEX_TRIGGER - 1
        male = create_voters(n_males, MALE)
        female = create_voters(n_females, FEMALE)

        voter_roll = male + female

        station = self.run_station_distributor(voter_roll, 1)[0]

        n_pages = generate_pdf_station_book(self.filename, station)

        self.assertFileExists(self.filename)

        # 5 pages = cover + 2 page males + 2 page females
        self.assertEqual(n_pages, 5)

    def test_generate_pdf_center_list_single_gender(self):
        """test generating a center list for a single gender station"""
        voter_roll = create_voters(10, MALE)

        stations = self.run_station_distributor(voter_roll, 1)

        n_pages = generate_pdf_center_list(self.filename, stations, MALE)

        self.assertFileExists(self.filename)

        # 2 pages = cover + 1 page males
        self.assertEqual(n_pages, 2)

    def test_generate_pdf_center_list_unisex(self):
        """test generating a center list for a unisex station"""
        n_voters = (settings.ROLLGEN_UNISEX_TRIGGER - 1) * 2
        voter_roll = create_voters(n_voters)

        stations = self.run_station_distributor(voter_roll, 1)

        n_pages = generate_pdf_center_list(self.filename, stations, UNISEX)

        self.assertFileExists(self.filename)

        # 5 pages = cover + 2 page males + 2 page females
        self.assertEqual(n_pages, 5)

    def test_generate_pdf_center_list_multiple_genders(self):
        """test generating a center list w/male & female stations"""
        n_voters = (settings.ROLLGEN_UNISEX_TRIGGER + 1) * 2
        voter_roll = create_voters(n_voters)

        stations = self.run_station_distributor(voter_roll, 2)

        n_pages = generate_pdf_center_list(self.filename, stations, MALE)

        self.assertFileExists(self.filename)

        # 3 pages = cover + 2 pages males
        self.assertEqual(n_pages, 3)

        n_pages = generate_pdf_center_list(self.filename, stations, FEMALE)

        self.assertFileExists(self.filename)

        # 3 pages = cover + 2 page females
        self.assertEqual(n_pages, 3)

    def test_generate_pdf_center_list_multiple_genders_multiple_stations(self):
        """test generating a center list w/multiple male & female stations

        This runs a code path that's not run when there's only one station of each gender.
        """
        # Ensure enough voters of each gender to spill over into a second station.
        n_males = n_females = settings.ROLLGEN_REGISTRANTS_PER_STATION_MAX + 1

        n_voters = n_males + n_females
        voter_roll = create_voters(n_voters)

        stations = self.run_station_distributor(voter_roll, 4)

        # Check males
        n_pages_actual = generate_pdf_center_list(self.filename, stations, MALE)
        self.assertFileExists(self.filename)
        # Roughly, n_pages_expected = cover + n_males / ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_LIST
        # However there's a page break at the end of each station so in the middle of the PDF where
        # it transitions from one station to another there will be one page with <
        # ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_LIST voters on it, unless the number of voters in
        # that station happens to be an exact multiple of
        # ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_LIST.
        n_pages_expected = 39
        self.assertEqual(n_pages_expected, n_pages_actual)

        # check females
        n_pages_actual = generate_pdf_center_list(self.filename, stations, FEMALE)
        self.assertFileExists(self.filename)
        self.assertEqual(n_pages_expected, n_pages_actual)


class TestGeneratePdfEdContent(TestGeneratePdfBase):
    """Compare the actual word-by-word content of the PDF with expected content."""
    def setUp(self):
        super(TestGeneratePdfEdContent, self).setUp()

        # Create a PDF that will spill to multiple pages.
        self.n_voters = settings.ROLLGEN_REGISTRATIONS_PER_PAGE_REGISTRATION + 1
        self.voter_roll = create_voters(self.n_voters, FEMALE)

    def test_sign_content(self):
        """Exercises generate_pdf_station_sign"""
        station = self.run_station_distributor(self.voter_roll, 1)[0]

        # Build a list of the lines I expect to see.
        expected_lines = []

        expected_lines.append(self.STRINGS['ed_polling_sign_header'])

        mf_string = self.STRINGS['female']

        # These are constructed "backwards" relative to how the actual code does it. It's
        # necessary to do so because the text is laid out RtoL in the PDF.
        center_name = apply_bidi(reshape(self.center.name))
        expected_lines.append('{} :{}'.format(center_name, self.STRINGS['center_name']))

        expected_lines.append('{} :{}'.format(self.center.center_id, self.STRINGS['center_number']))

        copied_by = self.center.copied_by.all()

        if self.center.copy_of:
            expected_lines.append('{} :{}'.format(self.center.copy_of.center_id,
                                                  self.STRINGS['copy_of']))
        elif copied_by:
            copied_by = [center.center_id for center in copied_by]
            copied_by = (' ' + ARABIC_COMMA).join(map(str, reversed(copied_by)))
            expected_lines.append('{} :{}'.format(copied_by, self.STRINGS['copied_by_plural']))

        expected_lines.append('{} {}{} {}'.format(str(station.number), NBSP, NBSP,
                                                  self.STRINGS['station_number']))

        expected_lines.append('{} :{}'.format(mf_string, self.STRINGS['gender']))

        expected_lines.append(self.STRINGS['names_range'])

        lines = station_name_range(station)
        expected_lines += format_station_name_range_lines(lines)

        # Now generate the actual PDF and compare to expected.
        n_pages = generate_pdf_station_sign(self.filename, station)
        self.assertEqual(n_pages, 1)

        # Now see what was actually in the PDF and compare to expected.
        xml = extract_pdf_page(self.filename, 0)
        textlines = extract_textlines(xml)
        actual_lines = clean_textlines(textlines)

        # Did center name wrap? If so, unwrap.
        if expected_lines[1].startswith(actual_lines[2]):
            actual_lines = unwrap_lines(actual_lines, 1)

        self.assertEqual(expected_lines, actual_lines)

        for textline in textlines:
            self.assertCorrectFontsInUse(textline)

    def test_sign_content_unisex(self):
        """Exercises generate_pdf_station_sign() with a unisex voter roll.

        This differs from male/female in that the first/last voter station names are more
        complicated, and long center names must be truncated.
        """
        # Create a center with a name that will cause problems if it isn't truncated.
        name_length = settings.ROLLGEN_CENTER_NAME_TRUNCATE_AFTER + 25
        center = RegistrationCenterFactory(name=generate_arabic_place_name(name_length))

        n_voters = (settings.ROLLGEN_UNISEX_TRIGGER - 1) * 2
        voter_roll = create_voters(n_voters)

        males = [voter for voter in voter_roll if voter.gender == MALE]
        females = [voter for voter in voter_roll if voter.gender == FEMALE]

        voter_roll = males + females

        station = self.run_station_distributor(voter_roll, 1)[0]
        station.center = center

        # Build a list of the lines I expect to see.
        expected_lines = []

        expected_lines.append(self.STRINGS['ed_polling_sign_header'])

        # These are constructed "backwards" relative to how the actual code does it. It's
        # necessary to do so because the text is laid out RtoL in the PDF.
        center_name = reshape(center.name)
        # Because gender is unisex, we have to truncate the center name
        center_name = apply_bidi(truncate_center_name(center_name))

        expected_lines.append('{} :{}'.format(center_name, self.STRINGS['center_name']))

        expected_lines.append('{} :{}'.format(center.center_id, self.STRINGS['center_number']))

        expected_lines.append('{} {}{} {}'.format(str(station.number), NBSP, NBSP,
                                                  self.STRINGS['station_number']))

        expected_lines.append('{} :{}'.format(self.STRINGS['unisex'], self.STRINGS['gender']))

        expected_lines.append(self.STRINGS['names_range'])

        lines = station_name_range(station)
        expected_lines += format_station_name_range_lines(lines)

        # Now generate the actual PDF and compare to expected.
        n_pages = generate_pdf_station_sign(self.filename, station)
        self.assertEqual(n_pages, 1)

        xml = extract_pdf_page(self.filename, 0)
        textlines = extract_textlines(xml)
        actual_lines = clean_textlines(textlines)

        self.assertEqual(expected_lines, actual_lines)

        for textline in textlines:
            self.assertCorrectFontsInUse(textline)

    def test_station_book_content_for_cover(self):
        """Exercises generate_pdf_station_book and checks cover content"""
        station = self.run_station_distributor(self.voter_roll, 1)[0]

        # Build a list of the lines I expect to see.
        expected_lines = []

        # The string ed_station_book_cover is a multiline string so it is stored in self.STRINGS
        # as a list of strings rather than just a simple string.
        expected_lines += self.STRINGS['ed_station_book_cover']

        mf_string = self.STRINGS['female']
        expected_lines.append('{} :{}'.format(mf_string, self.STRINGS['gender']))
        expected_lines.append('{} :{}'.format(self.center.center_id, self.STRINGS['center_number']))
        expected_lines.append('{} :{}'.format(apply_bidi(reshape(self.center.name)),
                                              self.STRINGS['center_name']))

        copied_by = self.center.copied_by.all()

        if self.center.copy_of:
            expected_lines.append('{} :{}'.format(self.center.copy_of.center_id,
                                                  self.STRINGS['copy_of']))
        elif copied_by:
            copied_by = [center.center_id for center in copied_by]
            copied_by = (' ' + ARABIC_COMMA).join(map(str, reversed(copied_by)))
            expected_lines.append('{} :{}'.format(copied_by, self.STRINGS['copied_by_plural']))

        subconstituency_id = self.center.subconstituency.id
        subconstituency_name = reshape(self.center.subconstituency.name_arabic)
        subconstituency_name = apply_bidi(subconstituency_name)
        subconstituency = '{} / {} :{}'.format(subconstituency_name, subconstituency_id,
                                               self.STRINGS['subconstituency_name'])
        expected_lines.append(subconstituency)

        expected_lines.append("{} {}{} {}".format(station.number, NBSP, NBSP,
                                                  self.STRINGS['station_number']))

        expected_lines.append(self.STRINGS['names_range'])

        lines = station_name_range(station)
        expected_lines += format_station_name_range_lines(lines)

        # Now generate the actual PDF and compare to expected.
        n_pages = generate_pdf_station_book(self.filename, station)
        self.assertEqual(n_pages, 3)

        xml = extract_pdf_page(self.filename, 0)

        textlines = extract_textlines(xml)
        actual_lines = clean_textlines(textlines)

        # Did center name wrap? If so, unwrap.
        if expected_lines[4].startswith(actual_lines[5]):
            actual_lines = unwrap_lines(actual_lines, 4)

        has_copy_info = (self.center.copy_of or self.center.copied_by)

        if has_copy_info:
            # Did copied by wrap?  If so, unwrap.
            if expected_lines[5].startswith(actual_lines[6]):
                actual_lines = unwrap_lines(actual_lines, 5)

        # Did subcon name wrap? If so, unwrap.
        offset = 1 if has_copy_info else 0
        if len(actual_lines) >= 7 + offset:
            if expected_lines[5 + offset].startswith(actual_lines[6 + offset]):
                actual_lines = unwrap_lines(actual_lines, 5 + offset)

        self.assertEqual(expected_lines, actual_lines)

        for textline in textlines:
            self.assertCorrectFontsInUse(textline)

    def test_station_book_content_for_inner_pages(self):
        """Exercises generate_pdf_station_book and checks content of non-cover pages"""
        station = self.run_station_distributor(self.voter_roll, 1)[0]

        # Build a list of the lines I expect to see.
        expected_lines = []

        page_header = []

        # Top header
        page_header.append(self.STRINGS['ed_list_header_prefix'])
        page_header.append(self.STRINGS['ed_station_book_header'])

        # Top right items
        mf_string = self.STRINGS['female']
        page_header.append('{} :{}'.format(mf_string, self.STRINGS['gender']))
        page_header.append('{} :{}'.format(self.center.center_id, self.STRINGS['center_number']))
        center_name = apply_bidi(truncate_center_name(reshape(self.center.name)))
        page_header.append('{} :{}'.format(center_name, self.STRINGS['center_name']))
        # Header just above table that contains voter names
        page_header.append("{} :{}".format(station.number, self.STRINGS['station_number']))

        expected_lines += page_header

        # Header for table of voter names
        # In the PDF these are in table cells so they're separate from one another; to my code
        # it looks as if they're adjacent.
        params = (self.STRINGS['voted'], self.STRINGS['the_names'], self.STRINGS['number'])
        expected_lines.append("{}{}{}".format(*params))

        # Voter data
        voters = station.roll[:settings.ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_BOOK]
        f = lambda voter: '{}{}'.format(apply_bidi(reshape(format_name(voter))),
                                        voter.registrant_number)
        expected_lines += [f(voter) for voter in voters]

        # Footer, including page #
        expected_lines.append(mf_string)
        expected_lines.append("2 / 1")

        # Now generate the actual PDF and compare to expected.
        n_pages = generate_pdf_station_book(self.filename, station)
        self.assertEqual(n_pages, 3)

        xml = extract_pdf_page(self.filename, 1)

        textlines = extract_textlines(xml)
        actual_lines = clean_textlines(textlines)

        self.assertEqual(expected_lines, actual_lines)

        for textline in textlines:
            self.assertCorrectFontsInUse(textline)

        # Test last page.
        expected_lines = []
        expected_lines += page_header

        # Header for table of voter names
        # In the PDF these are in table cells so they're separate from one another; to my code
        # it looks as if they're adjacent.
        params = (self.STRINGS['voted'], self.STRINGS['the_names'], self.STRINGS['number'])
        expected_lines.append("{}{}{}".format(*params))

        # Voter data
        # Get the voters for the last page. Negative slicing rocks!
        n_voters = len(self.voter_roll)
        n_last_page_voters = n_voters % settings.ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_BOOK
        voters = station.roll[-n_last_page_voters:]
        f = lambda voter: '{}{}'.format(apply_bidi(reshape(format_name(voter))),
                                        voter.registrant_number)
        expected_lines += map(f, voters)

        # Footer, including page #
        expected_lines.append(mf_string)
        expected_lines.append("2 / 2")

        # Now generate the actual PDF and compare to expected.
        n_pages = generate_pdf_station_book(self.filename, station)
        self.assertEqual(n_pages, 3)

        xml = extract_pdf_page(self.filename, 2)

        textlines = extract_textlines(xml)
        actual_lines = clean_textlines(textlines)

        self.assertEqual(expected_lines, actual_lines)

        for textline in textlines:
            self.assertCorrectFontsInUse(textline)

    def test_center_list_content_for_cover(self):
        """Exercises generate_pdf_center_list and checks cover content"""
        stations = self.run_station_distributor(self.voter_roll, 1)

        expected_lines = []
        expected_lines += self.STRINGS['ed_center_list_cover']

        key = 'female' if (self.gender == FEMALE) else 'male'
        mf_string = self.STRINGS[key]
        expected_lines.append('{} :{}'.format(mf_string, self.STRINGS['gender']))
        expected_lines.append('{} :{}'.format(self.center.center_id, self.STRINGS['center_number']))
        center_name = apply_bidi(reshape(self.center.name))
        expected_lines.append('{} :{}'.format(center_name, self.STRINGS['center_name']))

        copied_by = self.center.copied_by.all()
        if self.center.copy_of:
            expected_lines.append('{} :{}'.format(self.center.copy_of.center_id,
                                                  self.STRINGS['copy_of']))
        elif copied_by:
            copied_by = [center.center_id for center in copied_by]
            copied_by = (' ' + ARABIC_COMMA).join(map(str, reversed(copied_by)))
            expected_lines.append('{} :{}'.format(copied_by, self.STRINGS['copied_by_plural']))
        subconstituency_id = self.center.subconstituency.id
        subconstituency_name = reshape(self.center.subconstituency.name_arabic)
        subconstituency_name = apply_bidi(subconstituency_name)
        subconstituency = '{} / {} :{}'.format(subconstituency_name, subconstituency_id,
                                               self.STRINGS['subconstituency_name'])
        expected_lines.append(subconstituency)

        # Now generate the actual PDF and compare to expected.
        generate_pdf_center_list(self.filename, stations, self.gender)
        xml = extract_pdf_page(self.filename, 0)

        textlines = extract_textlines(xml)
        actual_lines = clean_textlines(textlines)

        # Did center name wrap? If so, unwrap.
        if expected_lines[4].startswith(actual_lines[5]):
            actual_lines = unwrap_lines(actual_lines, 4)

        has_copy_info = (self.center.copy_of or self.center.copied_by)

        if has_copy_info:
            # Did copied_by wrap? If so, unwrap.
            if expected_lines[5].startswith(actual_lines[6]):
                actual_lines = unwrap_lines(actual_lines, 5)

        # Did subcon name wrap? If so, unwrap.
        offset = 1 if has_copy_info else 0
        if len(actual_lines) >= 7 + offset:
            if expected_lines[5 + offset].startswith(actual_lines[6 + offset]):
                actual_lines = unwrap_lines(actual_lines, 5 + offset)

        self.assertEqual(expected_lines, actual_lines)

        for textline in textlines:
            self.assertCorrectFontsInUse(textline)

    def test_center_list_content_for_inner_pages(self):
        """Exercises generate_pdf_center_list and checks content of non-cover pages"""
        stations = self.run_station_distributor(self.voter_roll, 1)

        expected_lines = []

        page_header = []

        page_header.append(self.STRINGS['ed_list_header_prefix'])
        page_header.append(self.STRINGS['ed_center_list_header'])

        key = 'female' if (self.gender == FEMALE) else 'male'
        mf_string = self.STRINGS[key]
        page_header.append('{} :{}'.format(mf_string, self.STRINGS['gender']))
        page_header.append('{} :{}'.format(self.center.center_id, self.STRINGS['center_number']))
        center_name = apply_bidi(truncate_center_name(reshape(self.center.name)))
        page_header.append('{} :{}'.format(center_name, self.STRINGS['center_name']))

        expected_lines += page_header

        # Table header
        params = (self.STRINGS['station_header'], self.STRINGS['the_names'], self.STRINGS['number'])
        expected_lines.append('{}{}{}'.format(*params))

        # Voters
        station = stations[0]
        voters = station.roll[:settings.ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_LIST]
        f = lambda voter: '{}{}{}'.format(station.number,
                                          apply_bidi(reshape(format_name(voter))),
                                          voter.registrant_number)
        expected_lines += map(f, voters)

        # Footer, including page #
        expected_lines.append(mf_string)
        expected_lines.append("2 / 1")

        # Now generate the actual PDF and compare to expected.
        n_pages = generate_pdf_center_list(self.filename, stations, self.gender)
        self.assertEqual(n_pages, 3)

        xml = extract_pdf_page(self.filename, 1)

        textlines = extract_textlines(xml)
        actual_lines = clean_textlines(textlines)

        self.assertEqual(expected_lines, actual_lines)

        for textline in textlines:
            self.assertCorrectFontsInUse(textline)

        # Test last page.
        expected_lines = page_header

        # Table header
        params = (self.STRINGS['station_header'], self.STRINGS['the_names'], self.STRINGS['number'])
        expected_lines.append('{}{}{}'.format(*params))

        # Voter data
        # Get the voters for the last page. Negative slicing rocks!
        n_voters = len(self.voter_roll)
        n_last_page_voters = n_voters % settings.ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_LIST
        station = stations[0]
        voters = station.roll[-n_last_page_voters:]
        f = lambda voter: '{}{}{}'.format(station.number,
                                          apply_bidi(reshape(format_name(voter))),
                                          voter.registrant_number)
        expected_lines += map(f, voters)

        # Footer, including page #
        expected_lines.append(mf_string)
        expected_lines.append("2 / 2")

        # Now generate the actual PDF and compare to expected.
        n_pages = generate_pdf_center_list(self.filename, stations, self.gender)
        self.assertEqual(n_pages, 3)
        xml = extract_pdf_page(self.filename, 2)

        textlines = extract_textlines(xml)
        actual_lines = clean_textlines(textlines)

        self.assertEqual(expected_lines, actual_lines)

        for textline in textlines:
            self.assertCorrectFontsInUse(textline)


class TestCopiedBy(TestGeneratePdfEdContent):
    """A copy of TestGeneratePdfEdContent, but run with different data.

    This class uses a center that has one copy in order to exercise the copied_by code branch.
    """
    def setUp(self):
        super(TestCopiedBy, self).setUp()
        self.center = self.original_center

    # The methods below aren't affected by the copy_of/copied_by code so we don't need them
    # to do anything here.
    def test_sign_content_unisex(self):
        pass

    def test_station_book_content_for_inner_pages(self):
        pass

    def test_station_list_content_for_inner_pages(self):
        pass


class TestCopyOfCenter(TestGeneratePdfEdContent):
    """A copy of TestGeneratePdfEdContent, but run with different data.

    This class uses a center that is a copy in order to exercise the copy_of code branch.
    """
    def setUp(self):
        super(TestCopyOfCenter, self).setUp()
        # Any of the copy centers will do.
        self.center = self.copy_centers[2]

    # The methods below aren't affected by the copy_of/copied_by code so we don't need them
    # to do anything here.
    def test_sign_content_unisex(self):
        pass

    def test_station_book_content_for_inner_pages(self):
        pass

    def test_station_list_content_for_inner_pages(self):
        pass
