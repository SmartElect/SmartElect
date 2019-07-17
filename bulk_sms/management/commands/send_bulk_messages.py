import logging
import sys

from django.conf import settings
from django.core.management.base import BaseCommand

from bulk_sms.sending import MessageSendingLoop


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Long running process which sends out any approved bulk_sms messages at a maximum specified rate.
    This command calls low level RapidSMS API so will run in blocking fashion, even when the celery
    router is chosen. This is to ensure that we can catch errors/timeouts to prevent overwhelming
    downstream queues

    django-admin.py send_bulk_messages --forever

    This code is implemented in a management command rather than in Celery so that we can stop the
    outgoing messages if the batch is paused and have greater control over the rate at which
    messages are delivered than Celery rate limiting provides. While it is possible to implement
    similar functionality using groups and chords, the complexity is much greater with Celery
    than it is if we manually control message sending through a single parent process.
    """
    args = ''
    help = "Sends bulk_sms messages."

    def add_arguments(self, parser):
        parser.add_argument(
            '--messages-per-second',
            action='store',
            type=int,
            dest='msgs_per_sec',
            default=settings.BULKSMS_DEFAULT_MESSAGES_PER_SECOND,
            help='Maximum message send rate (msgs/s)')
        parser.add_argument(
            '--concurrent-workers',
            action='store',
            type=int,
            dest='concurrent_workers',
            default=settings.BULKSMS_DEFAULT_CONCURRENT_WORKERS,
            help='Number of worker threads or processes to use when sending messages (count)')
        parser.add_argument(
            '--forever',
            action='store_true',
            dest='send_forever',
            default=False,
            help='Set this option to loop indefinitely sending messages as they become available')

    def handle(self, *args, **options):
        msgs_per_sec = options['msgs_per_sec']
        concurrent_workers = options['concurrent_workers']
        send_forever = options['send_forever']
        # if we were called from the command line (and not from a unit test or
        # other Python method), show log messages on the console, too
        cmd_name = __name__.split('.')[-1]
        if cmd_name in sys.argv:
            logging.getLogger('bulk_sms').addHandler(logging.StreamHandler())
        # start the message sending loop, which returns after one group of
        # messages is sent if send_forever is False. Otherwise, it loops
        # indefinitely and returns only upon receipt of a SIGINT, SIGTERM, or SIGHUP
        mainloop = MessageSendingLoop(msgs_per_sec, concurrent_workers)
        mainloop.send(forever=send_forever)
