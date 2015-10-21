from django.core.exceptions import ValidationError
from django.test import TestCase

from .factories import DiscrepancyFactory, SMSTrailFactory, VumiLogFactory


class UnicodeMethodTest(TestCase):

    def test_vumilog(self):
        self.assertTrue(str(VumiLogFactory()))

    def test_smstrail(self):
        self.assertTrue(str(SMSTrailFactory()))

    def test_discrepancy(self):
        self.assertTrue(str(DiscrepancyFactory()))


class SMSTrailTest(TestCase):

    def test_report_if_both_sms_and_vumi_found(self):
        trail = SMSTrailFactory()
        # both sms.id and vumi.id should be in the report message (in the URLs)
        report = trail.report()
        self.assertIn(str(trail.sms.id), report)
        self.assertIn(str(trail.vumi.id), report)

    def test_report_if_only_sms_found(self):
        trail = SMSTrailFactory(vumi=None)
        # Only sms.id should be in the report message (in the URL)
        report = trail.report()
        self.assertIn(str(trail.sms.id), report)
        expected_regexp = r'^The .+ was sent by the registration system .+ but has not ' +\
                          'been received by the gateway system.$'
        self.assertRegexpMatches(report, expected_regexp)

    def test_report_if_only_vumi_found(self):
        trail = SMSTrailFactory(sms=None)
        # Only vumi.id should be in the report message (in the URL)
        report = trail.report()
        self.assertIn(str(trail.vumi.id), report)
        expected_regexp = r'^The .+ was received by the gateway system .+ but has not ' +\
                          'been received by the registration system.$'
        self.assertRegexpMatches(report, expected_regexp)

    def test_cant_save_unpopulated_instance(self):
        """Ensure one of sms or vumi must be populated before saving"""
        trail = SMSTrailFactory.build(sms=None, vumi=None)

        with self.assertRaises(ValidationError):
            trail.clean()


class DiscrepancyTest(TestCase):

    def test_discrepancy_trail_report(self):
        discrepancy = DiscrepancyFactory()
        self.assertEqual(discrepancy.trail_report(), discrepancy.trail.report())
