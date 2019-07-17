# 3rd party imports
from bidi.algorithm import get_display as apply_bidi

# Django imports
from django.conf import settings

# Project imports
from .base import TestGeneratePdfBase
from .factories import create_voters
from .utils_for_tests import extract_pdf_page, extract_textlines, clean_textlines, unwrap_lines
from ..arabic_reshaper import reshape
from ..generate_pdf import generate_pdf
from ..utils import truncate_center_name, format_name
from libya_elections.constants import ARABIC_COMMA, MALE, FEMALE, UNISEX


class TestGeneratePdfNoRegistrants(TestGeneratePdfBase):
    """Compare the word-by-word content of the PDF with expected content when there are no voters"""
    def setUp(self):
        super(TestGeneratePdfNoRegistrants, self).setUp()
        self.voter_roll = []

    def test_blank_page_content_male(self):
        """tests that the "blank" page explains why it is blank (no voters)"""
        generate_pdf(self.filename, self.center, self.voter_roll, MALE)

        # Build a list of the lines I expect to see.
        expected_lines = []
        expected_lines.append(self.STRINGS['center_header_prefix'])
        expected_lines.append(self.STRINGS['center_list_header'])
        expected_lines.append(self.STRINGS['no_male_registrants'])
        expected_lines.append("1 / 1")

        # Now see what was actually in the PDF and compare to expected.
        xml = extract_pdf_page(self.filename, 1)
        textlines = extract_textlines(xml)
        actual_lines = clean_textlines(textlines)

        self.assertEqual(expected_lines, actual_lines)

        for textline in textlines:
            self.assertCorrectFontsInUse(textline)

    def test_blank_page_content_female(self):
        """tests that the "blank" page explains why it is blank (no voters)"""
        # Build a list of the lines I expect to see.
        generate_pdf(self.filename, self.center, self.voter_roll, FEMALE)

        expected_lines = []
        expected_lines.append(self.STRINGS['center_header_prefix'])
        expected_lines.append(self.STRINGS['center_list_header'])
        expected_lines.append(self.STRINGS['no_female_registrants'])
        expected_lines.append("1 / 1")

        # Now see what was actually in the PDF and compare to expected.
        xml = extract_pdf_page(self.filename, 1)
        textlines = extract_textlines(xml)
        actual_lines = clean_textlines(textlines)

        self.assertEqual(expected_lines, actual_lines)

        for textline in textlines:
            self.assertCorrectFontsInUse(textline)


class TestGeneratePdfGenderParam(TestGeneratePdfBase):
    """Ensure that passing UNISEX to generate_pdf() raises an error.

    This is a small test that didn't seem to fit elsewhere.
    """
    def test_gender_param(self):
        self.voter_roll = create_voters(1, self.gender)
        with self.assertRaises(ValueError):
            generate_pdf(self.filename, self.center, self.voter_roll, UNISEX)


class GeneratePdfContentTestMixin(object):
    """Mixin the provides the main methods tested in several test cases in this file (below).

    These methods compare the actual word-by-word content of the PDF with expected content.

    There's no unisex tests needed here because that concept only matters when dealing with
    polling stations.
    """
    def test_cover_content(self):
        """tests that the cover page contains the expected text"""
        # Build a list of the lines I expect to see.
        expected_lines = []

        key = 'center_book_cover' if self.center_book else 'center_list_cover'
        expected_lines += self.STRINGS[key]

        # These are constructed "backwards" relative to how the actual code does it. It's
        # necessary to do so because the text is laid out RtoL in the PDF.
        expected_lines.append('{} :{}'.format(self.STRINGS['female'], self.STRINGS['gender']))

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

        # Now see what was actually in the PDF and compare to expected.
        xml = extract_pdf_page(self.filename, 0)
        textlines = extract_textlines(xml)

        actual_lines = clean_textlines(textlines)

        # Did center name wrap? If so, unwrap.
        if expected_lines[4].startswith(actual_lines[5]):
            actual_lines = unwrap_lines(actual_lines, 4)

        has_copy_info = (self.center.copy_of or self.center.copied_by)

        if has_copy_info:
            # Did center name wrap? If so, unwrap.
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

    def test_inner_page_content(self):
        """tests that the non-cover pages of a multipage PDF contain the expected text"""
        # 1 pages = cover + 2 pages of names
        self.assertEqual(self.n_pages, 3)

        # Build a list of the lines I expect to see. I don't care about the cover page, just
        # the inner pages.
        expected_lines = []

        page_header = []
        page_header.append(self.STRINGS['center_header_prefix'])
        key = 'center_book_header' if self.center_book else 'center_list_header'
        page_header.append(self.STRINGS[key])

        mf_string = self.STRINGS['female']

        page_header.append('{} :{}'.format(mf_string, self.STRINGS['gender']))

        page_header.append('{} :{}'.format(self.center.center_id, self.STRINGS['center_number']))

        center_name = apply_bidi(truncate_center_name(reshape(self.center.name)))
        page_header.append('{} :{}'.format(center_name, self.STRINGS['center_name']))

        expected_lines += page_header

        expected_lines.append(self.STRINGS['the_names'])

        for voter in self.voter_roll[:self.n_voters - 1]:
            expected_lines.append(apply_bidi(reshape(format_name(voter))))

        expected_lines.append(mf_string)

        # '2 / 1' is the 'page N/n_pages' from the footer
        expected_lines.append('2 / 1')

        # Now see what was actually in the PDF and compare to expected.
        xml = extract_pdf_page(self.filename, 1)
        textlines = extract_textlines(xml)
        actual_lines = clean_textlines(textlines)

        self.assertEqual(expected_lines, actual_lines)

        for textline in textlines:
            self.assertCorrectFontsInUse(textline)

        # OK now test the second (final) inner page. It only has one voter on it.
        expected_lines = page_header

        expected_lines.append(self.STRINGS['the_names'])

        for voter in self.voter_roll[-1:]:
            expected_lines.append(apply_bidi(reshape(format_name(voter))))

        expected_lines.append(mf_string)

        # '2 / 2' is the 'page N/n_pages' from the footer
        expected_lines.append('2 / 2')

        # Now see what was actually in the PDF and compare to expected.
        xml = extract_pdf_page(self.filename, 2)
        textlines = extract_textlines(xml)
        actual_lines = clean_textlines(textlines)

        self.assertEqual(expected_lines, actual_lines)

        for textline in textlines:
            self.assertCorrectFontsInUse(textline)


class TestGeneratePdfContentCenterList(TestGeneratePdfBase, GeneratePdfContentTestMixin):
    """Invoke GeneratePdfContentTestMixin for center lists.

    Center lists are only used during the in-person phase.
    """
    def setUp(self):
        super(TestGeneratePdfContentCenterList, self).setUp()
        self.center_book = False
        # Create a PDF that will spill to multiple pages.
        self.n_voters = settings.ROLLGEN_REGISTRATIONS_PER_PAGE_REGISTRATION + 1
        self.voter_roll = create_voters(self.n_voters, FEMALE)
        self.n_pages = generate_pdf(self.filename, self.center, self.voter_roll, FEMALE)


class TestGeneratePdfContentCenterBook(TestGeneratePdfBase):
    """Invoke GeneratePdfContentTestMixin for center books.

    Center books are only used during the exhibitions phase.
    """
    def setUp(self):
        super(TestGeneratePdfContentCenterBook, self).setUp()
        self.center_book = True
        self.n_pages = generate_pdf(self.filename, self.center, self.voter_roll, FEMALE)


class TestCopyOfCenter(TestGeneratePdfBase, GeneratePdfContentTestMixin):
    """Invoke GeneratePdfContentTestMixin for a copy center.

    This class uses a center that is a copy in order to exercise the copy_of code branch.
    """
    def setUp(self):
        super(TestCopyOfCenter, self).setUp()
        self.center_book = False
        self.n_voters = 5
        self.voter_roll = create_voters(self.n_voters, FEMALE)
        # Any of the copy centers will do.
        self.center = self.copy_centers[2]
        self.n_pages = generate_pdf(self.filename, self.center, self.voter_roll, FEMALE)

    def test_inner_page_content(self):
        # This doesn't need to be re-tested for copy centers; they only affect the cover page.
        self.assertTrue(True)


class TestCopiedByCenter(TestGeneratePdfBase, GeneratePdfContentTestMixin):
    """Invoke GeneratePdfContentTestMixin for a copied center.

    This class uses a center that is copied by other centers in order to exercise the copied_by
    code branch.
    """
    def setUp(self):
        super(TestCopiedByCenter, self).setUp()
        self.center_book = False
        self.n_voters = 5
        self.voter_roll = create_voters(self.n_voters, FEMALE)
        self.center = self.original_center
        self.n_pages = generate_pdf(self.filename, self.center, self.voter_roll, FEMALE)

    def test_inner_page_content(self):
        # This doesn't need to be re-tested for copy centers; they only affect the cover page.
        self.assertTrue(True)
