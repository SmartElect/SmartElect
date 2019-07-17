import os

from django import test
from django.conf import settings
from django.test.utils import override_settings
from django.utils.timezone import now

from audit.tests.factories import VumiLogFactory
from audit.models import VumiLog
from audit.parser import LogParser
from audit.tasks import parse_logs
from libya_elections.constants import INCOMING, OUTGOING


@override_settings(
    VUMI_LOGS=(
        os.path.join(settings.PROJECT_ROOT, 'audit', 'tests', 'inbound.txt'),
        os.path.join(settings.PROJECT_ROOT, 'audit', 'tests', 'outbound.txt'),
        # file does not exist
        os.path.join(settings.PROJECT_ROOT, 'audit', 'tests', 'fake.txt'),
    ),
    SHORT_CODES={'15015', '10030', '10050'}
)
class LogParserTest(test.TestCase):
    def setUp(self):
        self.date = now()
        self.uuid = 'b5c53932-b13b-4453-8b99-728e66d23062'
        self.raw_text = '2014-04-15T20:04:31+0200 [VumiRedis,client] Processed ' \
                        'inbound message for almadar_smpp_transport_15015: ' \
                        '{"transport_name": "almadar_smpp_transport_15015", ' \
                        '"in_reply_to": null, "group": null, "from_addr": ' \
                        '"218918510226", "timestamp": "2014-04-15 18:04:31.964560", ' \
                        '"to_addr": "15015", "content": "903039#1981", ' \
                        '"session_event": null, "routing_metadata": {}, ' \
                        '"message_version": "20110921", "transport_type": "sms", ' \
                        '"helper_metadata": {"rapidsms": {"rapidsms_msg_id": ' \
                        '"8b34b0971f9c412d84a2c58a9af5ed68"}}, "transport_metadata": {}, ' \
                        '"message_type": "user_message", ' \
                        '"message_id": "b5c53932-b13b-4453-8b99-728e66d23062"}'
        self.kwargs = {'message_id': self.uuid, 'to_addr': '15015'}
        self.parser = LogParser(direction=INCOMING)

    def test_save(self):
        # saves log entry to VumiLog table
        self.parser.save(self.date, self.raw_text, **self.kwargs)
        log_entries = VumiLog.objects.all()
        self.assertEqual(log_entries.count(), 1)

    def test_save_different_environment(self):
        # messages sent to a different environment are not saved
        self.kwargs['to_addr'] = '10020'  # testing
        self.parser.save(self.date, self.raw_text, **self.kwargs)
        log_entries = VumiLog.objects.all()
        self.assertEqual(log_entries.count(), 0)

    def test_uuid_already_in_db(self):
        VumiLogFactory(uuid=self.uuid)
        self.parser.save(self.date, self.raw_text, **self.kwargs)
        log_entries = VumiLog.objects.all()
        self.assertEqual(log_entries.count(), 1)

    def test_parse_line(self):
        # parsing a single line in the log file should create a VumiLog instance
        self.parser.parse_line(self.raw_text)
        log_entries = VumiLog.objects.all()
        self.assertEqual(log_entries.count(), 1)
        entry = log_entries[0]
        self.assertEqual(entry.uuid, self.uuid)
        self.assertEqual(entry.to_addr, '15015')
        self.assertEqual(entry.from_addr, '218918510226')
        self.assertEqual(entry.content, '903039#1981')

    def test_parse_line_old_format(self):
        # previous versions of Vumi/Twistd/Ubuntu logged the timestamp differently.
        # old: YYYY-MM-DD HH:MM:SS+0000
        # new  YYYY-MM-DDTHH:MM:SS+0000
        # Make sure we test the old format as well.

        # Put a space in location 10, replacing the 'T'
        old_text = self.raw_text[:10] + ' ' + self.raw_text[11:]
        self.parser = LogParser(direction=INCOMING)
        self.parser.parse_line(old_text)
        log_entries = VumiLog.objects.all()
        self.assertEqual(log_entries.count(), 1)
        entry = log_entries[0]
        self.assertEqual(entry.uuid, self.uuid)
        self.assertEqual(entry.to_addr, '15015')
        self.assertEqual(entry.from_addr, '218918510226')
        self.assertEqual(entry.content, '903039#1981')

    def test_parse_inbound(self):
        # parses log file for incoming messages. This file has 3 message sent to
        # the production short code and 2 to testing.
        self.parser.parse()
        log_entries = VumiLog.objects.filter(direction=INCOMING)
        self.assertEqual(log_entries.count(), 3)

    @override_settings(SHORT_CODES={'10020', '10040'})
    def test_parse_inbound_testing(self):
        # parses log file for incoming messages. This file has 3 message sent to
        # the production short code and 2 to testing.
        self.parser.parse()
        log_entries = VumiLog.objects.filter(direction=INCOMING)
        self.assertEqual(log_entries.count(), 2)

    def test_parse_outbound(self):
        # parses log file for incoming messages. File has 3 outgoing message
        # sent from a production short code and 1 from a testing short code.
        outgoing = OUTGOING
        parser = LogParser(direction=outgoing)
        parser.parse()
        log_entries = VumiLog.objects.filter(direction=outgoing)
        self.assertEqual(log_entries.count(), 3)

    @override_settings(SHORT_CODES={'10020', '10040'})
    def test_parse_outbound_testing(self):
        # parses log file for incoming messages. File has 3 outgoing message
        # sent from a production short code and 1 from a testing short code.
        outgoing = OUTGOING
        parser = LogParser(direction=outgoing)
        parser.parse()
        log_entries = VumiLog.objects.filter(direction=outgoing)
        self.assertEqual(log_entries.count(), 1)

    def test_parse_task(self):
        # File has 3 inbound and 3 outbound messages for production and
        # 2 inbound and 1 outbound for testing.
        parse_logs.delay()
        inbound = VumiLog.objects.filter(direction=INCOMING)
        outbound = VumiLog.objects.filter(direction=OUTGOING)
        self.assertEqual(inbound.count(), 3)
        self.assertEqual(outbound.count(), 3)

    @override_settings(SHORT_CODES={'10020', '10040'})
    def test_parse_task_testing(self):
        # File has 3 inbound and 3 outbound messages for production and
        # 2 inbound and 1 outbound for testing.
        parse_logs.delay()
        inbound = VumiLog.objects.filter(direction=INCOMING)
        outbound = VumiLog.objects.filter(direction=OUTGOING)
        self.assertEqual(inbound.count(), 2)
        self.assertEqual(outbound.count(), 1)
