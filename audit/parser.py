# based on the work by praekelt
# https://github.com/praekelt/vumi/blob/develop/vumi/scripts/parse_log_messages.py
from dateutil.parser import parse as dateutil_parse
import json
import logging
import re

from django.conf import settings

from libya_elections.constants import INCOMING

from .models import VumiLog

logger = logging.getLogger(__name__)

LOG_PATTERN = {
    'smpp_inbound': re.compile(
        r'(?P<date>[\d\-\+\:\s]+) .*'
        r'Processed inbound message .*?'
        r': (?P<message>.*)'),
    'smpp_outbound': re.compile(
        r'(?P<date>[\d\-\+\:\s]+) .*'
        r'Processed outbound message .*?'
        r': (?P<message>.*)'),
}


class LogParser(object):
    """
    Parses Vumi TransportUserMessages from a log file and saves log entries
    to the database in the VumiLog table.

    Two common output formats are the one used by SMPP for logging:

    `YYYY-MM-DD HH:MM:SS+0000 <bits of text> PUBLISHING INBOUND: {
        'from_addr': '218918510226',
        'to_addr': '10010', 'content': '903039#1981', 'transport_type': 'sms',
        'transport_metadata': {},
        'message_id': 'b5c53932-b13b-4453-8b99-728e66d23062'}`

    `YYYY-MM-DD HH:MM:SS+0000 <bits of text> Processed outbound message for <bits of text>: {
        "transport_name": "almadar_smpp_transport_10010",
        "in_reply_to": "b5c53932-b13b-4453-8b99-728e66d23062",
        "group": null,
        "from_addr": "10010",
        "timestamp": "2014-04-15 18:04:32.161446",
        "to_addr": "218918510226",
        "content": "",
        "routing_metadata": {"endpoint_name": "default"},
        "message_version": "20110921",
        "transport_type": "sms",
        "helper_metadata": {"rapidsms": {"rapidsms_msg_id": "8b34b0971f9c412d84a2c58a9af5ed65"}},
        "transport_metadata": {},
        "session_event": null,
        "message_id": "8b34b0971f9c412d64a2c58a9af5ed65",
        "message_type": "user_message"}'

    """
    def __init__(self, direction):
        self.direction = direction
        self.vumi_logs = settings.VUMI_LOGS
        if direction == INCOMING:
            self.log_pattern = LOG_PATTERN.get('smpp_inbound')
        else:
            self.log_pattern = LOG_PATTERN.get('smpp_outbound')

    def parse(self):
        """Open log files and parse them line by line."""
        for log in self.vumi_logs:
            try:
                with open(log) as log_file:
                    for line in log_file:
                        try:
                            self.parse_line(line)
                        except IndexError:
                            # if a exception is risen while parsing a line,
                            # we should continue parsing the file.
                            logger.info(u"Exception in line: {0}".format(line))
            except IOError as ex:
                # file does not exist
                logger.info(ex)

    def parse_line(self, line):
        """Parses and save a log entry to database. If there is more stuff being
        logged that will not match the regexp, those lines will be ignored."""
        match = self.log_pattern.match(line)
        if match:
            data = match.groupdict()
            date = dateutil_parse(data['date'])
            kwargs = json.loads(data['message'])
            logger.debug(u"parsing {0}".format(data['message']))
            self.save(date, line, **kwargs)

    def save(self, date, raw_text, **kwargs):
        """Saves parsed log entry to the db and returns the instance or None.

        Testing and production share a log file, only the log entries corresponding
        to the current environment are saved.
        """
        if self.direction == INCOMING:
            uuid = kwargs['message_id']
        else:
            # vumi stores the outgoing uuid in a different key
            uuid = kwargs['helper_metadata']['rapidsms']['rapidsms_msg_id']
        from_addr = kwargs.get('from_addr', '')
        to_addr = kwargs.get('to_addr', '')
        content = kwargs.get('content', '')
        short_codes = settings.SHORT_CODES
        if from_addr in short_codes or to_addr in short_codes:
            # If the short code used belongs to the right environment,
            # the log entry needs to be saved, and ignored otherwise.
            log, _ = VumiLog.objects.get_or_create(
                uuid=uuid,
                direction=self.direction,
                defaults={'logged_date': date, 'raw_text': raw_text, 'from_addr': from_addr,
                          'to_addr': to_addr, 'content': content}
            )
            return log
