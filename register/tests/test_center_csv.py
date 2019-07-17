import os
import shutil
import tempfile

from django.test import TestCase
from django.urls import reverse

from ..models import RegistrationCenter, Office, Constituency, SubConstituency
from .. import utils
from .factories import OfficeFactory, ConstituencyFactory, SubConstituencyFactory, \
    RegistrationCenterFactory
from libya_elections.constants import NO_NAMEDTHING
from staff.tests.base import StaffUserMixin


def get_copy_center_base_csv():
    """Return the base CSV for copy centers as a lists of lists (rows & columns)"""
    current_dir = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(current_dir, 'uploads', 'copy_center_base.csv')
    with open(file_path, 'rb') as f:
        lines = f.read().decode('utf-8').split('\n')
    return [line.split(',') for line in lines if line]


class CSVColumnConstants(object):
    """Constants mapping CSV columns to ints"""
    CENTER_ID = 0
    NAME = 1
    COPY_OF_ID = 2
    CENTER_TYPE = 12


class CenterFileTestMixin(object):
    def setUp(self):
        super(CenterFileTestMixin, self).setUp()
        self.url = reverse('upload-centers-csv')
        RegistrationCenterFactory(name="Deleted center", deleted=True)

    def tearDown(self):
        if hasattr(self, 'file'):
            self.file.close()

    def get_csv_file(self, filename):
        # generates a simple csv we can use for tests
        current_dir = os.path.dirname(os.path.realpath(__file__))
        file_path = os.path.join(current_dir, 'uploads', filename)
        self.file = open(file_path, 'rb')
        return self.file

    @staticmethod
    def get_messages(response):
        messages = response.context['messages']
        return [str(msg) for msg in messages]

    def upload_csv(self, filename='valid_ecc.csv', follow=True):
        csv_file = self.get_csv_file(filename)
        response = self.client.post(self.url, data={'csv': csv_file}, follow=follow)
        return response


class CenterFileUpload(CenterFileTestMixin, StaffUserMixin, TestCase):
    #  tests for the ecc file upload functionality
    permissions = ['add_registrationcenter']
    model = RegistrationCenter

    @classmethod
    def setUpClass(klass):  # Files only
        # Create a temp dir for CSV files created on the fly.
        klass.temp_dir = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(klass):  # Files only
        # Clean up temp CSV files.
        shutil.rmtree(klass.temp_dir)

    def setUp(self):
        super(CenterFileUpload, self).setUp()
        # Create some things
        for id in [1, NO_NAMEDTHING]:
            # create one test instance and one special 'no-named-thing' instance (999)
            if not Office.objects.filter(id=id).exists():
                OfficeFactory(id=id)
            if not Constituency.objects.filter(id=id).exists():
                ConstituencyFactory(id=id)
            if not SubConstituency.objects.filter(id=id).exists():
                SubConstituencyFactory(id=id)

    def write_csv(self, rows):
        """Given a list of lists, write them as a CSV to a temp file and return the filename.

        The list of lists should be rows and columns as returned by get_copy_center_base_csv().
        """
        fh, filename = tempfile.mkstemp(suffix='.csv', dir=self.temp_dir)
        os.close(fh)
        with open(filename, 'wb') as f:
            f.write('\n'.join([','.join(row) for row in rows]).encode('utf-8'))
        return filename

    def test_upload_page_works(self):
        # requesting the upload page works and the right template it's used
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'register/upload_centers_csv.html')

    def test_empty_upload(self):
        # form does not validate if an empty form it's submitted.
        # same template as the one we landed on it's used and the form
        # has an error.
        response = self.client.post(self.url, data={})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'register/upload_centers_csv.html')
        self.assertFormError(response, 'form', 'csv', 'This field is required.')

    def test_success_upload_page(self):
        # after successfully uploading a file we are presented with a
        # success template.
        response = self.upload_csv()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'register/upload_centers_csv.html')

    def test_upload_new_centers(self):
        # Uploading a csv file with new center information creates new entries
        # in the database.
        response = self.upload_csv()
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        self.assertEqual(centers.count(), 3)
        messages = self.get_messages(response)
        self.assertIn(
            utils.STATUS_MESSAGE.format(created=3, updated=0, dupes=0, blank=0),
            messages
        )

    def test_upload_dupes(self):
        # Upload does not create or update records if they did not change.
        response = self.upload_csv()
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        self.assertEqual(centers.count(), 3)
        response = self.upload_csv()
        messages = self.get_messages(response)
        self.assertIn(
            utils.STATUS_MESSAGE.format(created=0, updated=0, dupes=3, blank=0),
            messages
        )

    def test_upload_after_delete(self):
        # Upload, mark records deleted, upload again
        response = self.upload_csv()
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        self.assertEqual(centers.count(), 3)
        RegistrationCenter.objects.all().update(deleted=True)
        response = self.upload_csv()
        centers = RegistrationCenter.objects.all()
        self.assertEqual(centers.count(), 3)
        messages = self.get_messages(response)
        self.assertIn(
            utils.STATUS_MESSAGE.format(created=3, updated=0, dupes=0, blank=0),
            messages
        )

    def test_upload_update(self):
        # CSV updates a record if its attributes differ from those in the db.
        RegistrationCenter.objects.create(center_id=11001, name="Center 3")
        RegistrationCenter.objects.create(center_id=11001, name="Center 3", deleted=True)
        response = self.upload_csv()
        self.assertEqual(response.status_code, 200)
        reg_center = RegistrationCenter.objects.get(center_id=11001)
        self.assertNotEqual(reg_center.name, "Center 3")
        messages = self.get_messages(response)
        self.assertIn(
            utils.STATUS_MESSAGE.format(created=2, updated=1, dupes=0, blank=0),
            messages
        )

    def test_non_csv(self):
        # Non a CSV file should be generate a specific error.
        response = self.upload_csv(filename='icon_clock.gif')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        self.assertEqual(centers.count(), 0)
        messages = self.get_messages(response)
        self.assertIn(utils.COULD_NOT_PARSE_ERROR, messages)

    def test_bad_formatted_csv(self):
        # CSV files that contain rows with the wrong number of columns are not accepted.
        # Even compliant rows are not imported.
        response = self.upload_csv(filename='too_many_columns.csv')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        # file contained one valid center but it should not have been imported
        self.assertEqual(centers.count(), 0)
        messages = self.get_messages(response)
        self.assertIn(
            utils.PARSING_ERROR.format(line_number=2, columns=", ".join(utils.CSV_FIELDS)),
            messages[0]
        )

    def test_too_many_headers(self):
        # If the number of headers exceeds the number of columns expected,
        # fail gracefully and inform the user that their file has the wrong format
        response = self.upload_csv(filename='too_many_headers.csv')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        # Too many headers ==> entire file is rejected
        self.assertEqual(centers.count(), 0)
        messages = self.get_messages(response)
        self.assertIn(
            utils.PARSING_ERROR.format(line_number=1, columns=", ".join(utils.CSV_FIELDS)),
            messages[0]
        )

    def test_too_few_headers(self):
        # If the number of headers less than the number of columns expected,
        # fail gracefully and inform the user that their file has the wrong format
        response = self.upload_csv(filename='too_few_headers.csv')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        # Too few headers ==> entire file is rejected
        self.assertEqual(centers.count(), 0)
        messages = self.get_messages(response)
        self.assertIn(
            utils.PARSING_ERROR.format(line_number=1, columns=", ".join(utils.CSV_FIELDS)),
            messages[0]
        )

    def test_wrong_file_headers(self):
        # Uploading a csv file with columns in the wrong order should fail
        response = self.upload_csv(filename='wrong_headers.csv')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        # no centers were created because we encountered an error on line 1.
        self.assertEqual(centers.count(), 0)
        messages = self.get_messages(response)
        self.assertIn(
            utils.PARSING_ERROR.format(line_number=1, columns=", ".join(utils.CSV_FIELDS)),
            messages
        )

    def test_blank_csv(self):
        # Uploading a blank csv file should not create any centers
        response = self.upload_csv(filename='blank.csv')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        # No records were created
        self.assertEqual(centers.count(), 0)

    def test_blank_inbetween_csv(self):
        # Blank lines are valid in between two rows
        response = self.upload_csv(filename='blank_inbetween.csv')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        self.assertEqual(centers.count(), 5)
        messages = self.get_messages(response)
        self.assertIn(
            utils.STATUS_MESSAGE.format(created=5, updated=0, dupes=0, blank=3),
            messages
        )

    def test_noninteger_center_id_csv(self):
        # center id should be able to be cast into an integer otherwise a
        # parsing error will occur and a message indicating the line number
        # where the error occurred will be presented to the user.
        response = self.upload_csv(filename='noninteger_center_id.csv')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        # Due to error, no centers were created
        self.assertEqual(centers.count(), 0)
        messages = self.get_messages(response)
        self.assertIn(
            utils.FORM_FIELD_ERROR.format(field_name="center_id", value="110A1", line_number=2,
                                          error='Enter a whole number.'),
            messages[0]
        )

    def test_wrong_length_center_id_csv(self):
        response = self.upload_csv(filename='wrong_length_center_id.csv')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        # Due to error, no centers were created
        self.assertEqual(centers.count(), 0)
        messages = self.get_messages(response)
        self.assertIn(
            utils.FORM_FIELD_ERROR.format(field_name="center_id", value="110001", line_number=2,
                                          error='Ensure this value is less than or equal to'),
            messages[0]
        )

    def test_bad_office_id_csv(self):
        # office id should be able to be cast into an integer otherwise a
        # parsing error will occur and a message indicating the line number
        # where the error occurred will be presented to the user.
        response = self.upload_csv(filename='bad_office_id.csv')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        # Due to error, no centers were created
        self.assertEqual(centers.count(), 0)
        messages = self.get_messages(response)
        self.assertIn(
            utils.FORM_FIELD_ERROR.format(field_name="office_id", value="", line_number=2,
                                          error='This field is required.'),
            messages[0]
        )

    def test_centers_not_associated_with_office_con_subcon_csv(self):
        # Some Centers are not associated with offices, cons or subcons. For this purpose,
        # each of these NamedThing models has a special instance with an ID of NO_NAMEDTHING
        # (999) to represent the 'Absence of an associated NamedThing'.
        # https://github.com/hnec-vr/libya-elections/issues/949
        response = self.upload_csv(filename='no_associated_namedthings.csv')
        self.assertEqual(response.status_code, 200)
        # 1 center was created
        ecc = RegistrationCenter.objects.get()
        self.assertEqual(NO_NAMEDTHING, ecc.office.id)
        self.assertEqual(NO_NAMEDTHING, ecc.constituency.id)
        self.assertEqual(NO_NAMEDTHING, ecc.subconstituency.id)

    def test_bad_constituency_id_csv(self):
        # constituency id should be able to be cast into an integer otherwise a
        # parsing error will occur and a message indicating the line number
        # where the error occurred will be presented to the user.
        response = self.upload_csv(filename='bad_constituency_id.csv')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        # Due to error, no centers were created
        self.assertEqual(centers.count(), 0)
        messages = self.get_messages(response)
        self.assertIn(
            utils.FORM_FIELD_ERROR.format(field_name="constituency_id", value="x", line_number=2,
                                          error='Enter a whole number.'),
            messages[0]
        )

    def test_bad_subconstituency_id_csv(self):
        # subconstituency id should be able to be cast into an integer otherwise a
        # parsing error will occur and a message indicating the line number
        # where the error occurred will be presented to the user.
        response = self.upload_csv(filename='bad_subconstituency_id.csv')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        # Due to error, no centers were created
        self.assertEqual(centers.count(), 0)
        messages = self.get_messages(response)
        self.assertIn(
            utils.FORM_FIELD_ERROR.format(field_name="subconstituency_id", value="x", line_number=2,
                                          error='Enter a whole number.'),
            messages[0]
        )

    def test_just_one_latlong(self):
        # Providing just one of lat, long is an error
        response = self.upload_csv(filename='just_one_latlong.csv')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        # Due to error, no centers were created
        self.assertEqual(centers.count(), 0)
        messages = self.get_messages(response)
        self.assertIn(
            utils.FORM_ERROR.format(line_number=2,
                                    error='Either set both latitude and longitude or neither'),
            messages[0]
        )

    def test_invalid_lat(self):
        # Invalid latitude
        response = self.upload_csv(filename='invalid_lat.csv')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        # Due to error, no centers were created
        self.assertEqual(centers.count(), 0)
        messages = self.get_messages(response)
        self.assertIn(
            utils.FORM_FIELD_ERROR.format(
                line_number=2, field_name='center_lat', value="1234",
                error='Ensure that there are no more than 3 digits before the decimal'),
            messages[0]
        )

    def test_nonexistent_office(self):
        response = self.upload_csv(filename='nonexistent_office.csv')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        # Due to error, no centers were created
        self.assertEqual(centers.count(), 0)
        messages = self.get_messages(response)
        self.assertIn(
            utils.FORM_FIELD_ERROR.format(
                line_number=2, field_name='office_id', value='22',
                error='Office does not exist.'),
            messages[0]
        )

    def test_nonexistent_constituency(self):
        response = self.upload_csv(filename='nonexistent_constituency.csv')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        # Due to error, no centers were created
        self.assertEqual(centers.count(), 0)
        messages = self.get_messages(response)
        self.assertIn(
            utils.FORM_FIELD_ERROR.format(
                line_number=2, field_name='constituency_id', value='22',
                error='Constituency does not exist.'),
            messages[0]
        )

    def test_nonexistent_subconstituency(self):
        response = self.upload_csv(filename='nonexistent_subconstituency.csv')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        # Due to error, no centers were created
        self.assertEqual(centers.count(), 0)
        messages = self.get_messages(response)
        self.assertIn(
            utils.FORM_FIELD_ERROR.format(
                line_number=2, field_name='subconstituency_id', value='22',
                error='Subconstituency does not exist.'),
            messages[0]
        )

    def test_blank_center_name(self):
        response = self.upload_csv(filename='blank_center_name.csv')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        # Due to error, no centers were created
        self.assertEqual(centers.count(), 0)
        messages = self.get_messages(response)
        self.assertIn(
            utils.FORM_FIELD_ERROR.format(
                line_number=2, field_name='name', value='',
                error='This field is required.'),
            messages[0]
        )

    def test_newline_in_center_name(self):
        response = self.upload_csv(filename='newline_center_name.csv')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        # Due to error, no centers were created
        self.assertEqual(centers.count(), 0)
        messages = self.get_messages(response)
        self.assertIn(
            utils.FORM_FIELD_ERROR.format(
                line_number=2, field_name='name', value='new\nline',
                error='Newlines are not allowed.'),
            messages[0]
        )

    def test_reg_open_field_set_to_true(self):
        # The 'reg_open' field is not included in the CSV file.
        # We should ensure that it is set to True (the model default)
        response = self.upload_csv()
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        self.assertEqual(centers.count(), 3)
        for ecc in centers:
            self.assertEqual(ecc.reg_open, True)

    def test_simple_copy_center_ok(self):
        # test that simple copy center creation works
        RegistrationCenterFactory(center_id=70001)

        csv = get_copy_center_base_csv()
        csv[1][CSVColumnConstants.COPY_OF_ID] = '70001'
        csv[1][CSVColumnConstants.CENTER_TYPE] = \
            RegistrationCenter.Types.NAMES['ar'][RegistrationCenter.Types.COPY]

        response = self.upload_csv(filename=self.write_csv(csv))
        self.assertEqual(response.status_code, 200)

        centers = RegistrationCenter.objects.all()
        self.assertEqual(len(centers), 2)
        self.assertEqual(centers[0].copy_of, centers[1])
        self.assertEqual(list(centers[1].copied_by.all()), [centers[0]])

    def test_copy_center_same_file_reference_ok(self):
        # test that a copy center can reference an original created in the same file
        csv = get_copy_center_base_csv()
        # Duplicate the data row and make row the 2nd data row refer to the first.
        csv.append(csv[1][::])
        csv[2][CSVColumnConstants.CENTER_ID] = '70002'
        csv[2][CSVColumnConstants.COPY_OF_ID] = '70000'
        csv[2][CSVColumnConstants.CENTER_TYPE] = \
            RegistrationCenter.Types.NAMES['ar'][RegistrationCenter.Types.COPY]

        response = self.upload_csv(filename=self.write_csv(csv))
        self.assertEqual(response.status_code, 200)

        centers = RegistrationCenter.objects.all()
        self.assertEqual(len(centers), 2)
        self.assertEqual(centers[1].copy_of, centers[0])
        self.assertEqual(list(centers[0].copied_by.all()), [centers[1]])

    def test_copy_center_failed_reference(self):
        # test that one can't create a copy center that refers to a non-existent center.
        csv = get_copy_center_base_csv()
        csv[1][CSVColumnConstants.COPY_OF_ID] = '70001'
        response = self.upload_csv(filename=self.write_csv(csv))
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        # Due to error, no centers were created
        self.assertEqual(centers.count(), 0)
        messages = self.get_messages(response)
        self.assertIn(
            utils.FORM_FIELD_ERROR.format(
                line_number=2, field_name='copy_of_id', value='70001',
                error='Copy centre does not exist.'),
            messages[0]
        )

    def test_copy_center_read_only(self):
        # test that copy centers are read only
        original_center = RegistrationCenterFactory(center_id=70000)
        copy_center = RegistrationCenterFactory(center_id=70001)
        copy_center.copy_of = original_center
        copy_center.save()

        csv = get_copy_center_base_csv()
        csv[1][CSVColumnConstants.CENTER_ID] = '70001'
        csv[1][CSVColumnConstants.NAME] = 'different_name_to_trigger_an_attempt_to_edit'
        csv[1][CSVColumnConstants.COPY_OF_ID] = '70000'
        response = self.upload_csv(filename=self.write_csv(csv))
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        self.assertListEqual([center.center_id for center in centers], [70000, 70001])

        messages = self.get_messages(response)
        self.assertIn(
            utils.FORM_ERROR.format(
                line_number=2, error='Copy centres are read-only.'),
            messages[0]
        )

    def test_existing_center_cant_become_copy_center(self):
        # test that an existing center can't be turned into a copy center.
        RegistrationCenterFactory(center_id=70000)
        RegistrationCenterFactory(center_id=70001)
        csv = get_copy_center_base_csv()
        csv[1][CSVColumnConstants.COPY_OF_ID] = '70001'
        csv[1][CSVColumnConstants.CENTER_TYPE] = \
            RegistrationCenter.Types.NAMES['en'][RegistrationCenter.Types.COPY]
        response = self.upload_csv(filename=self.write_csv(csv))
        self.assertEqual(response.status_code, 200)
        # No new centers should have been created
        centers = RegistrationCenter.objects.all()
        self.assertListEqual([center.center_id for center in centers], [70000, 70001])

        messages = self.get_messages(response)
        self.assertIn(
            utils.FORM_ERROR.format(
                line_number=2, error='A centre may not be changed to a copy centre.'),
            messages[0]
        )

    def test_existing_center_must_remain_copy_center(self):
        # test that an existing copy center can't become a non-copy center.
        original_center = RegistrationCenterFactory(center_id=70000)
        copy_center = RegistrationCenterFactory(center_id=70001)
        copy_center.copy_of = original_center
        copy_center.save()

        csv = get_copy_center_base_csv()
        csv[1][CSVColumnConstants.CENTER_ID] = '70001'
        csv[1][CSVColumnConstants.COPY_OF_ID] = ''
        csv[1][CSVColumnConstants.CENTER_TYPE] = \
            RegistrationCenter.Types.NAMES['en'][RegistrationCenter.Types.GENERAL]
        response = self.upload_csv(filename=self.write_csv(csv))
        self.assertEqual(response.status_code, 200)
        # No new centers should have been created
        centers = RegistrationCenter.objects.all()
        self.assertListEqual([center.center_id for center in centers], [70000, 70001])

        messages = self.get_messages(response)
        self.assertIn(
            utils.FORM_ERROR.format(
                line_number=2, error='Copy centres are read-only.'),
            messages[0]
        )

    def test_center_type_valid(self):
        # In the CSV file, 'center_type' is an arabic string field. We should
        # parse it and convert to a corresponding integer from RegistrationCenter.Types.CHOICES.
        response = self.upload_csv(filename='valid_center_types.csv')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        self.assertEqual(centers.count(), 13)
        # The first 6 centers in the test CSV have Arabic names. (At present we don't have have
        # an Arabic translation for "Split" so there's no point in testing it.)
        for i, center in enumerate(centers[:6]):
            self.assertEqual(center.center_type, RegistrationCenter.Types.CHOICES[i][0])
        # The last 7 centers in the test CSV have English names.
        for i, center in enumerate(centers[6:]):
            self.assertEqual(center.center_type, RegistrationCenter.Types.CHOICES[i][0])

    def test_center_type_invalid(self):
        # If we don't recognize the value in the 'center_type' field, then return an error.
        response = self.upload_csv(filename='invalid_center_types.csv')
        self.assertEqual(response.status_code, 200)
        centers = RegistrationCenter.objects.all()
        self.assertEqual(centers.count(), 0)
        messages = self.get_messages(response)
        self.assertIn(
            utils.FORM_FIELD_ERROR.format(
                line_number=2, field_name='center_type', value='invalid_center_type',
                error='That is not a valid center_type'),
            messages[0]
        )

    def test_center_type_copy_required_for_copy_centers(self):
        # Copy centers must have the copy center type
        RegistrationCenterFactory(center_id=70000)

        csv = get_copy_center_base_csv()
        csv[1][CSVColumnConstants.CENTER_ID] = '70001'
        csv[1][CSVColumnConstants.COPY_OF_ID] = '70000'
        csv[1][CSVColumnConstants.CENTER_TYPE] = \
            RegistrationCenter.Types.NAMES['ar'][RegistrationCenter.Types.OIL]

        response = self.upload_csv(filename=self.write_csv(csv))
        self.assertEqual(response.status_code, 200)
        # No new centers should have been created
        centers = RegistrationCenter.objects.all()
        self.assertListEqual([center.center_id for center in centers], [70000])

        messages = self.get_messages(response)
        self.assertIn(
            utils.FORM_ERROR.format(
                line_number=2, error='Copy centre type must be "copy".'),
            messages[0]
        )

    def test_center_type_copy_rejected_for_noncopy_centers(self):
        # Non-copy centers may not have the copy center type
        csv = get_copy_center_base_csv()
        csv[1][CSVColumnConstants.CENTER_TYPE] = \
            RegistrationCenter.Types.NAMES['ar'][RegistrationCenter.Types.COPY]

        response = self.upload_csv(filename=self.write_csv(csv))
        self.assertEqual(response.status_code, 200)
        # No new centers should have been created
        centers = RegistrationCenter.objects.all()
        self.assertEqual(len(centers), 0)

        messages = self.get_messages(response)
        self.assertIn(
            utils.FORM_ERROR.format(
                line_number=2, error='Centre type "copy" requires copy centre information.'),
            messages[0]
        )
