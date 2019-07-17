# -*- coding: utf-8 -*-

# Python imports
import os
import shutil
import tempfile
import urllib.parse

# 3rd party imports
from bidi.algorithm import get_display as apply_bidi

# Django imports
from django.conf import settings
from django.test import TestCase
from django.urls import reverse

# Project imports
from .factories import create_voters, generate_arabic_place_name
from .utils_for_tests import clean_font_name, EXPECTED_FONTS
from ..constants import METADATA_FILENAME, ROLLGEN_FLAG_FILENAME
from ..job import INPUT_ARGUMENTS_TEMPLATE
from ..models import station_distributor
from ..strings import STRINGS
from libya_elections.constants import FEMALE
from libya_site.tests.factories import UserFactory
from register.tests.factories import RegistrationCenterFactory, SubConstituencyFactory
from voting.tests.factories import ElectionFactory


class ResponseCheckerMixin(object):
    """Mixin for TestCase classes; provides more explicit response testing"""
    def assertResponseOK(self, response):
        """Given a response, test that it is a 200"""
        self.assertEqual(200, response.status_code)

    def assertResponseForbidden(self, response):
        """Given a response, test that it is a 403"""
        self.assertEqual(403, response.status_code)

    def assertResponseNotFound(self, response):
        """Given a response, test that it is a 403"""
        self.assertEqual(404, response.status_code)

    def assertResponseRedirectsToLogin(self, response):
        """Given a response, test that it is a redirect to the login page"""
        self.assertEqual(302, response.status_code)
        self.assertEqual(urllib.parse.urlparse(response.url).path, reverse(settings.LOGIN_URL))


class TestJobBase(TestCase):
    def setUp(self):
        self.election = ElectionFactory()

        self.center = RegistrationCenterFactory(name=generate_arabic_place_name())
        self.office_id = self.center.office.id

        # Create a bunch of voters registered at each of these centers. The number of voters
        # matters somewhat.
        # station_distributor() will create a unisex station under certain conditions if
        # there are < N male or female voters, where N = UNISEX_TRIGGER (currently 25). The
        # names of the generated PDFs (which this code tests) have the gender embedded, so if I
        # change the # of voters and that causes a unisex station to be created, the filenames of
        # the generated PDFs will be different than these tests expect so the tests will fail.
        # I use a number of voters that guarantees I won't create a unisex station.
        n_voters = (settings.ROLLGEN_UNISEX_TRIGGER * 2) + 2

        self.voters = create_voters(n_voters, center=self.center)

        self.password = 'alligators'
        self.user = UserFactory(password=self.password)

        # Each test gets a fresh work dir.
        self.output_path = tempfile.mkdtemp()
        self.input_arguments = INPUT_ARGUMENTS_TEMPLATE.copy()
        self.input_arguments['center_ids'] = [self.center.center_id]

    def tearDown(self):
        # Clean up.
        shutil.rmtree(self.output_path)

    def get_standard_manifest(self, phase):
        """Given the phase, return a list of standard files generated during that phase.

        Each phase (in_person, exhibitions, polling) has certain files that are always
        generated. This convenience function enumerates them.
        """
        manifest = [ROLLGEN_FLAG_FILENAME, METADATA_FILENAME, METADATA_FILENAME + '.sha256',
                    str(self.office_id) + '.zip']
        if phase == 'polling':
            manifest += ['voters_by_national_id.csv', 'voters_by_center_and_station.csv', ]

        return [(filename, 'file') for filename in manifest]

    def assertExpectedNamesMatchActual(self, expected_names):
        """Given a list of expected file/dir names, compare them to the actual output.

        The input is a list of 2-tuples of (name, type) where name is the unqualified name of a
        file or directory and type is one of ('file', 'dir').

        This code detects errors of omission as well as spurious files.
        """
        # Fully qualify the expected names with the output path and sort so that they're in
        # a predictable order.
        expected_names = [(os.path.join(self.output_path, name), type_) for name, type_ in
                          expected_names]
        expected_names.sort()

        # Get actual names from file system and sort so that they're in a predictable order.
        actual_names = []
        for directory in os.walk(self.output_path):
            root_dirname, contained_dirs, contained_files = directory
            for dirname in contained_dirs:
                dirname = os.path.join(root_dirname, dirname)
                actual_names.append((dirname, 'dir'))

            for filename in contained_files:
                filename = os.path.join(root_dirname, filename)
                actual_names.append((filename, 'file'))

        actual_names.sort()

        # Compare.
        self.assertListEqual(expected_names, actual_names)

    def assertNotCalled(self, mocks):
        """Given a list of function mocks, ensures that each was not called."""
        for mock in mocks:
            assert not mock.called, "Unexpected call to mock"


class TestGeneratePdfBase(TestCase):
    """Base class helpers for PDF generation tests"""

    @classmethod
    def setUpClass(cls):
        # Create a temp dir for my mess.
        cls.temp_dir = tempfile.mkdtemp()

        with tempfile.NamedTemporaryFile(suffix='.pdf', dir=cls.temp_dir, delete=False) as f:
            cls.filename = f.name

        cls.gender = FEMALE

        cls.STRINGS = {}

        # Each of the strings in the STRINGS variable that I get from utils need the same
        # transformations applied to get them to match what comes out of the PDF. First, they
        # need to be reversed (because the Arabic text is RtoL in the PDF) and second, the
        # HTML-ish <br> elements need to become newlines.
        for key, value in STRINGS.items():
            value = value.split('<br/>')
            value = [''.join(apply_bidi(line)) for line in value if line]
            # If this is a list of only one line, leave it as a simple string.
            if len(value) == 1:
                value = value[0]
            cls.STRINGS[key] = value

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir)

    def setUp(self):
        subconstituency_name = os.environ.get('ROLLGEN_TEST_SUBCONSTITUENCY_NAME', '')

        if not subconstituency_name:
            subconstituency_name = generate_arabic_place_name()

        center_name = os.environ.get('ROLLGEN_TEST_CENTER_NAME', '')

        if not center_name:
            center_name = generate_arabic_place_name()

        subconstituency = SubConstituencyFactory(name_arabic=subconstituency_name)

        self.center = RegistrationCenterFactory(subconstituency=subconstituency, name=center_name)

        # For the center that has copies, I give it the max number of copies possible in order
        # to force the 'copied by' string to be as long as possible to reveal any line wrapping
        # problems that result.
        self.original_center = RegistrationCenterFactory()
        self.copy_centers = RegistrationCenterFactory.create_batch(settings.N_MAX_COPY_CENTERS,
                                                                   copy_of=self.original_center)

        self.election = ElectionFactory()

    def assertFileExists(self, filename):
        """assert that the given file exists"""
        self.assertTrue(os.path.isfile(filename))

    def assertCorrectFontsInUse(self, textline):
        """assert that the textline characters are in the correct font"""
        actual_fonts = set([text_element.get('font') for text_element in textline])

        # Clean names and remove None if present.
        actual_fonts = [clean_font_name(font_name) for font_name in actual_fonts if font_name]

        for font_name in actual_fonts:
            self.assertIn(font_name, EXPECTED_FONTS)

    def run_station_distributor(self, voter_roll, expected_length=-1):
        """Runs station_distributor() on the roll, and sets the election and center on each station.

        If expected_length is not the default of -1, this method will also assert that the list
        of stations return by station_distributor() is the correct length.
        """
        stations = station_distributor(voter_roll)
        for station in stations:
            station.election = self.election
            station.center = self.center

        if expected_length != -1:
            self.assertEqual(len(stations), expected_length)

        return stations
