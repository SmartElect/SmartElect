from unittest.mock import patch

from django.test import TestCase

from ..forms import NewJobForm
from libya_elections.constants import CENTER_ID_LENGTH


class NewJobFormTestCase(TestCase):
    def test_simple_case_ok(self):
        """test simple positive case of form submission"""
        data = {
            'name': 'abdefg',
            'phase': 'polling',
            'center_selection_type': 'all',
        }
        form = NewJobForm(data=data)
        self.assertTrue(form.is_valid())

    def test_job_name_must_be_valid(self):
        """Exercise validate_job_name() for name validity"""
        data = {
            'name': '.',
            'phase': 'polling',
            'center_selection_type': 'all',
        }
        form = NewJobForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(['name'], list(form.errors.keys()))
        self.assertEqual([['"." is not a valid job name.']], list(form.errors.values()))

    @patch('rollgen.forms.is_rollgen_output_dir')
    def test_job_name_must_be_unused(self, mock_is_rollgen_output_dir):
        """Exercise validate_job_name() for name uniqueness"""
        mock_is_rollgen_output_dir.return_value = True
        data = {
            'name': 'Sue',
            'phase': 'polling',
            'center_selection_type': 'all',
        }
        form = NewJobForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(['name'], list(form.errors.keys()))
        self.assertEqual([['There is already a job named "Sue".']], list(form.errors.values()))

    def test_center_type_required(self):
        """Ensure center type is required"""
        data = {
            'name': 'abdefg',
            'phase': 'polling',
        }
        form = NewJobForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(['center_selection_type'], list(form.errors.keys()))
        self.assertEqual([['This field is required.']], list(form.errors.values()))

    def test_office_required(self):
        """Ensure one or more offices must be selected w/center_selection_type=by_office"""
        data = {
            'name': 'abdefg',
            'phase': 'polling',
            'center_selection_type': 'by_office',
        }
        form = NewJobForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(['offices'], list(form.errors.keys()))
        self.assertEqual([['You must select at least one office.']], list(form.errors.values()))

    def test_constituency_required(self):
        """Ensure 1+ constituencies must be selected w/center_selection_type=by_constituency"""
        data = {
            'name': 'abdefg',
            'phase': 'polling',
            'center_selection_type': 'by_constituency',
        }
        form = NewJobForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(['constituencies'], list(form.errors.keys()))
        self.assertEqual([['You must select at least one constituency.']],
                         list(form.errors.values()))

    def test_center_select_list_required(self):
        """Ensure 1+ centers must be selected w/center_selection_type=by_center_select_list"""
        data = {
            'name': 'abdefg',
            'phase': 'polling',
            'center_selection_type': 'by_center_select_list',
        }
        form = NewJobForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(['center_select_list'], list(form.errors.keys()))
        self.assertEqual([['You must select at least one centre.']], list(form.errors.values()))

    def test_center_text_list_required(self):
        """Ensure 1+ centers must be selected w/center_selection_type=by_center_text_list"""
        data = {
            'name': 'abdefg',
            'phase': 'polling',
            'center_selection_type': 'by_center_text_list',
        }
        form = NewJobForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(['center_text_list'], list(form.errors.keys()))
        self.assertEqual([['You must enter at least one centre.']], list(form.errors.values()))

    def test_center_text_list_valid(self):
        """Ensure center ids in center_text_list are checked for validity"""
        data = {
            'name': 'abdefg',
            'phase': 'polling',
            'center_selection_type': 'by_center_text_list',
            'center_text_list': 'abc',
        }
        form = NewJobForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(['center_text_list'], list(form.errors.keys()))
        self.assertEqual([['These ids are invalid: abc']], list(form.errors.values()))

    def test_center_text_list_real_center_id(self):
        """Ensure center ids in center_text_list are checked to ensure they exist"""
        center_id = '1' * CENTER_ID_LENGTH
        data = {
            'name': 'abdefg',
            'phase': 'polling',
            'center_selection_type': 'by_center_text_list',
            'center_text_list': center_id,
        }
        form = NewJobForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(['center_text_list'], list(form.errors.keys()))
        self.assertEqual([['These centre ids are invalid: {}'.format(center_id)]],
                         list(form.errors.values()))
