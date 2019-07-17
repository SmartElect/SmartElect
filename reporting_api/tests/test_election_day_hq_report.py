# Python imports
from datetime import timedelta

# Django imports
from django.test import TestCase
from django.utils.timezone import now

# Project imports
from civil_registry.tests.factories import CitizenFactory
from libya_elections.constants import FIRST_PERIOD_NUMBER, LAST_PERIOD_NUMBER
from register.models import RegistrationCenter, Office
from register.tests.factories import OfficeFactory, RegistrationFactory, \
    RegistrationCenterFactory, SMSFactory
from polling_reports.models import CenterClosedForElection
from polling_reports.tests.factories import CenterOpenFactory, PollingReportFactory
from voting.tests.factories import ElectionFactory
from reporting_api.data_pull_ed import generate_election_day_hq_reports


class TestElectionDayHQReport(TestCase):
    """Exercise generate_election_day_hq_reports()"""
    def setUp(self):
        self.registrations_per_center = 4

        self.oil_center_period_1_voters = 1
        self.oil_center_period_2_voters = 2
        self.offices = [OfficeFactory(region=Office.REGION_EAST),
                        OfficeFactory(region=Office.REGION_WEST),
                        ]
        # Note: An oil center doesn't normally allow registrations, but it does so for
        # this testcase.
        self.oil_center = RegistrationCenterFactory(office=self.offices[0],
                                                    center_type=RegistrationCenter.Types.OIL)

        # !reg_open won't affect election day counts but it will affect whether
        # or not any registrations are found
        self.inactive_for_reg_center = RegistrationCenterFactory(office=self.offices[1],
                                                                 reg_open=False)

        self.centers = [self.oil_center,
                        RegistrationCenterFactory(office=self.offices[0]),
                        RegistrationCenterFactory(office=self.offices[0]),
                        RegistrationCenterFactory(office=self.offices[1]),
                        self.inactive_for_reg_center,
                        ]

        copy_center = RegistrationCenterFactory(office=self.offices[1], copy_of=self.centers[3])
        self.centers.append(copy_center)

        self.election_decoy_before = ElectionFactory(
            name_english='decoy before',
            name_arabic='decoy before (ar)',
            polling_start_time=now() - timedelta(days=10),
            polling_end_time=now() - timedelta(days=9),
        )
        self.election = ElectionFactory(
            name_english='%s election' % type(self).__name__,
            name_arabic='not Arabic',
            polling_start_time=now() - timedelta(hours=2),
            polling_end_time=now() + timedelta(hours=2),
        )
        self.election_decoy_after = ElectionFactory(
            name_english='decoy after',
            name_arabic='decoy after (ar)',
            polling_start_time=now() + timedelta(days=9),
            polling_end_time=now() + timedelta(days=10),
        )

        self.center_opens = []
        for center in self.centers:
            if center != self.centers[1]:
                self.center_opens.append(CenterOpenFactory(election=self.election,
                                                           registration_center=center))

        # CenterOpen may refer to a deleted center. Make sure that we don't find those
        self.deleted_center = RegistrationCenterFactory(office=self.offices[0], deleted=True)
        self.center_open_referring_to_deleted_center = CenterOpenFactory(
            election=self.election,
            registration_center=self.deleted_center)

        # Performance enhancement: this dummy person and SMS allow me to avoid creation of two
        # spurious objects for each registration I create.
        self.citizen = CitizenFactory()
        self.sms = SMSFactory(citizen=self.citizen)

        # Create registrations, but be careful not to create any at the copy center
        # or at the center which doesn't support registrations.
        self.registrations = []
        for center in self.centers:
            if center.reg_open and not center.copy_of:
                self.registrations += \
                    RegistrationFactory.create_batch(self.registrations_per_center,
                                                     citizen=self.citizen,
                                                     sms=self.sms,
                                                     registration_center=center)

        # These reports include quirks such as multiple reports for a center (very common in real
        # life), a missing final period report, and multiple reports for the same center & period.
        self.reports = [
            PollingReportFactory(election=self.election,
                                 registration_center=self.oil_center,
                                 period_number=FIRST_PERIOD_NUMBER,
                                 num_voters=self.oil_center_period_1_voters),
            PollingReportFactory(election=self.election,
                                 registration_center=self.oil_center,
                                 period_number=FIRST_PERIOD_NUMBER + 1,
                                 num_voters=self.oil_center_period_2_voters),
            PollingReportFactory(election=self.election,
                                 registration_center=self.centers[2],
                                 period_number=FIRST_PERIOD_NUMBER,
                                 num_voters=1),
            # The next two reports are for the same center & period with different num_voters
            # to exercise the code that sorts by modification_date.
            PollingReportFactory(election=self.election,
                                 registration_center=self.centers[2],
                                 period_number=FIRST_PERIOD_NUMBER + 1,
                                 num_voters=4),
            PollingReportFactory(election=self.election,
                                 registration_center=self.centers[2],
                                 period_number=FIRST_PERIOD_NUMBER + 1,
                                 num_voters=6),
            PollingReportFactory(election=self.election,
                                 registration_center=self.centers[3],
                                 period_number=FIRST_PERIOD_NUMBER,
                                 num_voters=1),
            PollingReportFactory(election=self.election,
                                 registration_center=self.centers[3],
                                 period_number=FIRST_PERIOD_NUMBER + 1,
                                 num_voters=4),
            # This report for a deleted center should be ignored
            PollingReportFactory(election=self.election,
                                 registration_center=self.deleted_center,
                                 period_number=FIRST_PERIOD_NUMBER + 1,
                                 num_voters=50),
            PollingReportFactory(election=self.election,
                                 registration_center=self.inactive_for_reg_center,
                                 period_number=FIRST_PERIOD_NUMBER + 1,
                                 num_voters=50),
            # This report for a copy center should count towards the original/parent center
            PollingReportFactory(election=self.election,
                                 registration_center=copy_center,
                                 period_number=LAST_PERIOD_NUMBER,
                                 num_voters=1),
        ]

        self.result = generate_election_day_hq_reports(self.election)
        # Create an alternate result which reflects that the "oil center" is
        # marked inactive for this election.
        self.inactive_on_election = CenterClosedForElection(
            registration_center=self.oil_center, election=self.election
        )
        self.inactive_on_election.full_clean()
        self.inactive_on_election.save()
        self.result_with_inactive = generate_election_day_hq_reports(self.election)

    def test_top_level_keys_and_totals(self):
        """Test that generate_election_day_hq_reports() returns a dict with the right keys.

        Also test national totals.
        """
        report_types = sorted(('by_office', 'by_region', 'by_center_type', 'national', ))
        self.assertEqual(sorted(self.result.keys()), report_types)

        self.assertEqual(self.result['national']['r']['open'], 12)
        self.assertEqual(self.result['national']['r']['active'], 16)
        self.assertEqual(self.result['national']['v'], 63)

    def test_report_by_office(self):
        """Exercise generate_election_day_hq_reports() by office"""
        result = self.result['by_office']
        expected_offices = [str(office.id) for office in self.offices]
        self.assertEqual(sorted(result.keys()), sorted(expected_offices))

        self.assertEqual(result[str(self.offices[0].id)]['r']['open'], 8)
        self.assertEqual(result[str(self.offices[0].id)]['r']['active'], 12)
        self.assertEqual(result[str(self.offices[0].id)]['v'], 8)
        self.assertEqual(result[str(self.offices[1].id)]['r']['open'], 4)
        self.assertEqual(result[str(self.offices[1].id)]['r']['active'], 4)
        self.assertEqual(result[str(self.offices[1].id)]['v'], 55)

    def test_report_by_region(self):
        """Exercise generate_election_day_hq_reports() by region"""
        result = self.result['by_region']
        expected_regions = [str(region) for region in sorted(Office.ALL_REGIONS)]
        self.assertEqual(sorted(result.keys()), expected_regions)

        for region in Office.ALL_REGIONS:
            region = str(region)
            if int(region) == Office.REGION_EAST:
                self.assertEqual(result[region]['r']['open'], 8)
                self.assertEqual(result[region]['r']['active'], 12)
                self.assertEqual(result[region]['v'], 8)
            elif int(region) == Office.REGION_WEST:
                self.assertEqual(result[region]['r']['open'], 4)
                self.assertEqual(result[region]['r']['active'], 4)
                self.assertEqual(result[region]['v'], 55)
            else:
                self.assertEqual(result[region]['r']['open'], 0)
                self.assertEqual(result[region]['r']['active'], 0)
                self.assertEqual(result[region]['v'], 0)

    def test_report_by_center_type(self):
        """Exercise generate_election_day_hq_reports() by center type"""
        result = self.result['by_center_type']

        expected_types = sorted([center_type for center_type in RegistrationCenter.Types.ALL if
                                 center_type != RegistrationCenter.Types.COPY])
        expected_types = [str(center_type) for center_type in expected_types]
        self.assertEqual(sorted(result.keys()), expected_types)

        # either 'v' (for vote count) which is a leaf node, or 'r' (for
        # registration count) which has leaf nodes 'open' and 'active'.
        for center_type in result:
            center_type = str(center_type)
            if int(center_type) == RegistrationCenter.Types.GENERAL:
                self.assertEqual(result[center_type]['r']['open'], 8)
                self.assertEqual(result[center_type]['r']['active'], 12)
                self.assertEqual(result[center_type]['v'], 61)
            elif int(center_type) == RegistrationCenter.Types.OIL:
                self.assertEqual(result[center_type]['r']['open'], 4)
                self.assertEqual(result[center_type]['r']['active'], 4)
                self.assertEqual(result[center_type]['v'], 2)
            else:
                self.assertEqual(result[center_type]['r']['open'], 0)
                self.assertEqual(result[center_type]['r']['active'], 0)
                self.assertEqual(result[center_type]['v'], 0)

    def test_report_with_inactive_center(self):
        """Verify report reflecting a center being inactive for this specific election"""
        # Adjust the results gathered with the oil center inactive so that they
        # "should" match the results with it active, then compare.
        by_oil_center_type = \
            self.result_with_inactive['by_center_type'][str(RegistrationCenter.Types.OIL)]
        by_office_of_oil_center = \
            self.result_with_inactive['by_office'][str(self.oil_center.office_id)]
        by_region_of_oil_center = \
            self.result_with_inactive['by_region'][str(self.oil_center.office.region)]
        national = self.result_with_inactive['national']

        for d in (by_oil_center_type, by_office_of_oil_center, by_region_of_oil_center, national):
            d['r']['open'] += self.registrations_per_center
            d['v'] += self.oil_center_period_2_voters

        self.assertDictEqual(self.result, self.result_with_inactive)
