import csv
from io import StringIO
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils.translation import ugettext as _

from libya_site.tests.factories import DEFAULT_USER_PASSWORD, UserFactory
from register.tests.factories import RegistrationCenterFactory
from reporting_api.constants import POLLING_CENTER_CODE


class CSVReportTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.staff_user = UserFactory()
        cls.staff_user.is_staff = True
        cls.staff_user.save()

    def setUp(self):
        assert self.client.login(username=self.staff_user.username, password=DEFAULT_USER_PASSWORD)

    def _request_csv(self, url):
        """
        Use the test client to request a URL and parse the response body as CSV, return a list of
        rows.

        Note: These reports are actually Tab-separated, for historical reasons, but we currently
        refer to them as CSV everywhere.
        """
        self.rsp = self.client.get(url)
        if self.rsp.status_code == 200:
            reader = csv.reader(StringIO(self.rsp.content.decode('utf-16')), delimiter='\t')
            return list(reader)

    @patch('vr_dashboard.views.views.retrieve_report')
    def test_daily_csv_bad_dates(self, mock_retrieve_report):
        # mock the reports so we don't get a 503 if they don't exist
        mock_daily_by_office_report = []
        mock_daily_by_subconstituency_report = []
        mock_metadata_report = {
            'last_updated': '2018-02-27',
        }
        mock_retrieve_report.return_value = [
            mock_daily_by_office_report,
            mock_daily_by_subconstituency_report,
            mock_metadata_report,
        ]
        # daily_csv validates the dates given to it
        url = reverse(
            'vr_dashboard:daily-csv-with-dates',
            kwargs={'from_date': '99/03/2018', 'to_date': '02/03/2018'})
        self._request_csv(url)
        self.assertEqual(self.rsp.status_code, 400)

    @patch('vr_dashboard.views.views.retrieve_report')
    def test_daily_csv_is_correct(self, mock_retrieve_report):
        mock_daily_by_office_report = [
            ['EN', 'AR', '13/03/2018 (M)', '13/03/2018 (F)'],
            ['Office 2', '', 3, 4],
        ]
        mock_daily_by_subconstituency_report = [
            ['EN', 'AR', '13/03/2018 (M)', '13/03/2018 (F)'],
            ['Subcon 2', '', 3, 4],
        ]
        mock_metadata_report = {
            'last_updated': '2018-02-27',
        }
        mock_retrieve_report.return_value = [
            mock_daily_by_office_report,
            mock_daily_by_subconstituency_report,
            mock_metadata_report,
        ]
        url = reverse('vr_dashboard:daily-csv')
        rows = self._request_csv(url)
        self.assertEqual(
            rows,
            [
                ['Last Updated: 00:00 27-02-2018'],
                ['Office', '13/03/2018 (M)', '13/03/2018 (F)'],
                ['Office 2', '3', '4'],
                [],
                ['Subconstituency', '13/03/2018 (M)', '13/03/2018 (F)'],
                ['Subcon 2', '3', '4']
            ]
        )

    @patch('vr_dashboard.views.views.retrieve_report')
    def test_daily_csv_with_dates_is_correct(self, mock_retrieve_report):
        # We have report data from Feb 28 to Mar 3
        mock_daily_by_office_report = [
            ['EN', 'AR', '28/02/2018 (M)', '01/03/2018 (F)', '02/03/2018 (F)', '03/03/2018 (F)'],
            ['Office 2', '', 3, 4, 5, 6],
        ]
        mock_daily_by_subconstituency_report = [
            ['EN', 'AR', '28/02/2018 (M)', '01/03/2018 (F)', '02/03/2018 (F)', '03/03/2018 (F)'],
            ['Subcon 2', '', 3, 4, 5, 6],
        ]
        mock_metadata_report = {
            'last_updated': '2018-02-27',
        }
        mock_retrieve_report.return_value = [
            mock_daily_by_office_report,
            mock_daily_by_subconstituency_report,
            mock_metadata_report,
        ]
        # We only ask for data from Mar 1 to Mar 2
        url = reverse(
            'vr_dashboard:daily-csv-with-dates',
            kwargs={'from_date': '01/03/2018', 'to_date': '02/03/2018'})
        rows = self._request_csv(url)
        # We only have the columns we expect:
        self.assertEqual(
            rows,
            [
                ['Last Updated: 00:00 27-02-2018'],
                ['Office', '01/03/2018 (F)', '02/03/2018 (F)'],
                ['Office 2', '4', '5'],
                [],
                ['Subconstituency', '01/03/2018 (F)', '02/03/2018 (F)'],
                ['Subcon 2', '4', '5']
            ]
        )

    @patch('vr_dashboard.views.views.retrieve_report')
    def test_center_csv_is_correct(self, mock_retrieve_report):
        center1 = RegistrationCenterFactory()
        center2 = RegistrationCenterFactory()
        # add a center which is not in the Redis report, so won't be in the CSV report
        RegistrationCenterFactory()

        # Mock the Redis reports
        mock_metadata_report = {
            'last_updated': '2018-02-27',
        }
        mock_center_report = [
            {POLLING_CENTER_CODE: center1.center_id, 'total': 88},
            {POLLING_CENTER_CODE: center2.center_id, 'total': 999},
        ]
        mock_retrieve_report.return_value = [mock_metadata_report, mock_center_report]

        # Get the CSV report
        url = reverse('vr_dashboard:center-csv')
        rows = self._request_csv(url)

        # First row is the 'Last Updated' message
        self.assertTrue(rows[0][0].startswith('Last Updated:'))

        # Second row are the headers
        self.assertEqual(rows[1], [_("Center ID"), _("Name"), _("Total Registrations")])

        # There are 2 data rows
        self.assertEqual(rows[2], [str(center1.center_id), center1.name, str(88)])
        self.assertEqual(rows[3], [str(center2.center_id), center2.name, str(999)])

        # And that's it. The third center is not included in the report
        self.assertEqual(len(rows), 4)

    @patch('vr_dashboard.views.views.retrieve_report')
    def test_phone_csv_is_correct(self, mock_retrieve_report):
        # Mock the Redis reports
        mock_metadata_report = {
            'last_updated': '2018-02-27',
        }
        mock_phone_report = [
            ['9195551212', 3],
            ['9198675309', 13],
        ]
        mock_retrieve_report.return_value = [mock_metadata_report, mock_phone_report]

        # Get the CSV report
        url = reverse('vr_dashboard:phone-csv')
        rows = self._request_csv(url)

        # First row is the 'Last Updated' message
        self.assertTrue(rows[0][0].startswith('Last Updated:'))

        # Second row are the headers
        self.assertEqual(rows[1], [_("Phone Number"), _("Total Registrations")])

        # There are 2 data rows, with each column converted to str
        self.assertEqual(rows[2], [str(item) for item in mock_phone_report[0]])
        self.assertEqual(rows[3], [str(item) for item in mock_phone_report[1]])
