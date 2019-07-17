from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse

from libya_site.tests.factories import UserFactory, DEFAULT_USER_PASSWORD


@patch('vr_dashboard.views.views.retrieve_report')
class ReportsViewPostTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff_user = UserFactory()
        cls.staff_user.is_staff = True
        cls.staff_user.save()
        cls.c = Client()  # One client / session / login for all the tests
        assert cls.c.login(username=cls.staff_user.username, password=DEFAULT_USER_PASSWORD)

        # Mock stats for retrieve_report to return
        mock_stats = {
            'headline': {
                'males': 1,
                'females': 1,
            }
        }
        mock_metadata_report = {
            'last_updated': '2018-02-27',
        }
        cls.test_reports = [
            mock_stats,
            mock_metadata_report,
        ]

    def test_reports_view_get(self, mock_retrieve_report):
        mock_retrieve_report.return_value = self.test_reports
        rsp = self.c.get(reverse('vr_dashboard:reports'))
        self.assertEqual(200, rsp.status_code, msg=rsp.content.decode('utf-8'))
        context = rsp.context
        # Should have a form to submit a date-limited daily csv request
        self.assertIn('start_end_report_form', context)

    def test_reports_view_post_no_dates(self, mock_retrieve_report):
        # Posting without any dates is a 400
        mock_retrieve_report.return_value = self.test_reports
        rsp = self.c.post(reverse('vr_dashboard:reports'))
        self.assertEqual(400, rsp.status_code)
        form = rsp.context['start_end_report_form']
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {'from_date': ['This field is required.'], 'to_date': ['This field is required.']},
            form.errors)

    def test_reports_view_post_only_start_date(self, mock_retrieve_report):
        # Posting with only one date is a 400
        mock_retrieve_report.return_value = self.test_reports
        data = {
            'from_date': '30/03/2018',
        }
        rsp = self.c.post(reverse('vr_dashboard:reports'), data)
        self.assertEqual(400, rsp.status_code)
        form = rsp.context['start_end_report_form']
        self.assertFalse(form.is_valid())
        self.assertEqual({'to_date': ['This field is required.']}, form.errors)

    def test_reports_view_post_only_end_date(self, mock_retrieve_report):
        # Posting with only one date is a 400
        mock_retrieve_report.return_value = self.test_reports
        data = {
            'to_date': '30/03/2018',
        }
        rsp = self.c.post(reverse('vr_dashboard:reports'), data)
        self.assertEqual(400, rsp.status_code)
        form = rsp.context['start_end_report_form']
        self.assertFalse(form.is_valid())
        self.assertEqual({'from_date': ['This field is required.']}, form.errors)

    def test_reports_view_post_invalid_dates(self, mock_retrieve_report):
        # An invalid date is a 400
        mock_retrieve_report.return_value = self.test_reports
        data = {
            # Expecting dd/mm/yyyy.  03/30/2018 is not valid for that format,
            # but would be an easy mistake to make for us
            'from_date': '03/30/2018',
            'to_date': '01/04/2018',
        }
        rsp = self.c.post(reverse('vr_dashboard:reports'), data)
        self.assertEqual(400, rsp.status_code)
        form = rsp.context['start_end_report_form']
        self.assertFalse(form.is_valid())
        self.assertEqual({'from_date': ['Enter a valid date.']}, form.errors)

    def test_reports_view_post_valid_dates(self, mock_retrieve_report):
        # Valid dates return a redirect
        mock_retrieve_report.return_value = self.test_reports
        data = {
            'from_date': '30/03/2018',
            'to_date': '01/04/2018',
        }
        rsp = self.c.post(
            reverse('vr_dashboard:reports'), data,
            follow=False
        )
        expected_url = reverse('vr_dashboard:daily-csv-with-dates', kwargs=data)
        self.assertRedirects(rsp, expected_url, fetch_redirect_response=False)
