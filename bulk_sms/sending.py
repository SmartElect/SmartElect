import logging
import os
import time
import signal
import multiprocessing

from django.conf import settings
from django.core.cache import cache
from django.db import connections as django_db_connections
from django.db.models import F

from rapidsms.errors import MessageSendingError
from rapidsms.router import get_router

from bulk_sms.utils import concurrency_safe_by_args, signal_manager
from bulk_sms.models import Batch, BulkMessage
from libya_elections.phone_numbers import best_connection_for_phone_number


logger = logging.getLogger(__name__)

__all__ = ('MessageSendingLoop', 'send_messages', 'send_message_by_id',)

# Target number of seconds to spend sending a group of messages. This should
# be lower than the period supervisord waits to send a SIGKILL after sending a
# SIGTERM, otherwise we risk getting killed in the middle of sending messages.
# Supervisor's default for this is 10 seconds (see ``stopwaitsecs`` on:
# http://supervisord.org/configuration.html#program-x-section-values).
# Note that this is not truly a maximum, since if Vumi is responding slower than
# we expect, we don't check the elapsed time and exit early.
SECONDS_PER_GROUP = 5

# Maximum number of messages to send from a child process before that process
# is restarted.
MAX_MESSAGES_PER_CHILD = 10000


class MessageSendingLoop(object):
    # signals we know how to handle gracefully:
    signals = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)

    def __init__(self, msgs_per_sec=50, concurrent_workers=1):
        super(MessageSendingLoop, self).__init__()
        # save our PID on start-up so we know who is the parent process later
        self._parent_pid = os.getpid()
        # save __init__ arguments
        self.num_to_send = msgs_per_sec * SECONDS_PER_GROUP
        self.concurrent_workers = concurrent_workers
        # initialize instance variables in case methods that use them are called
        # out of sequence
        self._running = False

    def _signal_handler(self, signum, frame):
        """
        Handle any of the signals in ``self.signals`` by setting
        ``self._running`` to ``False``.
        """
        # ignore signal if not received in the parent process
        if os.getpid() != self._parent_pid:
            logger.debug('Ignoring signal %s in child process.' % signum)
            return
        # set a flag so self.send() will exit as soon as it's finished current work (if any)
        if self._running:
            logger.debug('Received signal %s. Set _running = False.' % signum)
            self._running = False
        else:
            logger.debug('Received signal %s; ignored because not running or '
                         'shutdown already in process.' % signum)

    def _install_signal_handlers(self):
        """
        Install signal handlers for the signals we know how to handle gracefully.
        """
        logger.debug('Installing signal handlers.')
        for sig in self.signals:
            signal_manager.push(sig, self._signal_handler)

    def _restore_signal_handlers(self):
        """
        Restore the saved signal handlers that we replaced in
        ``_install_signal_handlers``, if any.
        """
        logger.debug('Restoring original signal handlers.')
        for sig in self.signals:
            signal_manager.pop(sig)

    def _create_pool(self):
        """
        Create a multiprocessing worker pool for sending bulk messages.
        """
        # close database connections manually to make sure they're not passed
        # to subprocesses
        logger.debug('Closing database connections before starting worker pool.')
        for conn in django_db_connections.all():
            conn.close()
        cache.close()
        # send the messages in parallel using ``concurrent_workers`` processes. use
        # multiprocessing rather than threads so we don't have to clean
        # up database connections that the threads might leave open.
        logger.debug('Starting worker pool with {0} processes.'.format(self.concurrent_workers))
        return multiprocessing.Pool(processes=self.concurrent_workers,
                                    maxtasksperchild=MAX_MESSAGES_PER_CHILD)

    def send(self, forever=False):
        """
        Watch for new bulk SMS batches to send. If ``forever`` is ``True``,
        wait indefinitely or until we receive a signal, which should be handled
        by ``self._signal_handler``. If ``forever`` is ``False``, wait only until
        a single run through the loop finishes, and then return.
        """
        self._running = True
        # install signal handlers before creating the pool so that we can ignore them
        # in child processes (instead of exiting by accident)
        self._install_signal_handlers()
        pool = self._create_pool()
        try:
            while self._running:
                start = time.time()
                num_sent = 0
                batch = Batch.objects.get_next_batch()
                if batch:
                    num_sent = send_messages(batch, num_to_send=self.num_to_send, map_=pool.map)
                time_taken = time.time() - start
                if num_sent > 0:
                    logger.info("Sent %d messages. Time taken: %.2f seconds"
                                % (num_sent, time_taken))
                if not forever:
                    break
                # sleep for one second at a time so we can exit sooner if
                # self._running is set to False
                while self._running and (time.time() - start) < SECONDS_PER_GROUP:
                    time.sleep(1)
        finally:
            # close the pool and wait for subprocesses to exit
            logger.debug('Waiting for pool to shut down...')
            pool.close()
            logger.debug('Pool closed for new work; waiting for join() to complete...')
            pool.join()
            logger.debug('Pool shutdown complete.')
            # wait to restore signal handlers until we've done all the clean up
            # we need to, so that we're not killed in the middle of it
            self._restore_signal_handlers()


def send_messages(batch, num_to_send=250, map_=map):
    """
    Send ``num_to_send`` oldest messages from the specified ``batch``. If none
    left to send, update status to COMPLETED. Return the number of messages sent.

    If supplied, ``map_`` must be a method that behaves like the ``map``
    build-in. A parallelized version, e.g., ``multiprocessing.Pool.map``,
    can be used to improve message sending throughput.
    """
    message_pks = batch.messages.unsent().values_list('id', flat=True)[:num_to_send]
    num_sent = sum(map_(send_message_by_id, message_pks))
    errors = len(message_pks) - num_sent
    # check to see if we sent all the messages yet
    if not batch.messages.unsent().exists():
        # no messages, Batch is complete
        Batch.objects.filter(pk=batch.pk).update(status=Batch.COMPLETED)
    if errors:
        Batch.objects.filter(pk=batch.pk).update(errors=F('errors') + errors)
    return num_sent


# make sure no one else calls this method with the same arguments at the same
# time, i.e., make sure we don't accidentally send the same message twice. this
# most likely will never occur, but could happen, e.g., if more than one copy
# of the send_bulk_messages management command is running at a time
@concurrency_safe_by_args(timeout=60, default=0)
def send_message_by_id(bmsg_pk):
    """
    Send a specific ``BulkMessage`` object based on the provided primary key,
    ``bmsg_pk``. Intended to be called from a separate process or thread that
    might not inherit the caller's database connection.

    Returns the number of messages sent (0 or 1).
    """
    num_sent = 0
    try:
        # include a few sanity checks when retrieving this message, just in case
        # the database changed since this ``bmsg_pk`` was queued
        bmsg = BulkMessage.objects.unsent().select_related('batch')\
                          .get(pk=bmsg_pk, batch__status=Batch.APPROVED)
    except BulkMessage.DoesNotExist:
        bmsg = None
    if bmsg:
        try:
            out_msg = send_one_message(bmsg.from_shortcode, bmsg.phone_number, bmsg.message)
        except MessageSendingError:
            logger.exception("Error sending bulk_sms message: id %d, batch %s" %
                             (bmsg.pk, bmsg.batch))
        else:
            if out_msg:
                num_sent = 1
                BulkMessage.objects.filter(pk=bmsg_pk).update(sms=out_msg.sms)
    return num_sent


def send_one_message(from_number, to_number, message, message_code=None):
    """
    Can raise MessageSendingError.

    Returns the sent message (out_msg) if sent, None if process_outgoing_phases returned False so
    the message was not sent.

    If message_code is provided, add that to the message, so our SMS object gets populated with it.

    :param from_number:
    :type from_number: string
    :param to_number:
    :type to_number: string
    :param message:
    :type message: string
    :param message_code:
    :type message_code: integer
    """
    connection = best_connection_for_phone_number(to_number, settings.BULKSMS_BACKENDS)
    # create a RapidSMS message object
    router = get_router()
    out_msg = router.new_outgoing_message(text=message, connections=[connection])
    # setup the from_number
    out_msg.fields['endpoint'] = from_number
    # add the message_code if we know it
    if message_code:
        out_msg.fields['message_code'] = message_code
    # process the RapidSMS outgoing phases
    continue_sending = router.process_outgoing_phases(out_msg)
    if continue_sending:
        router.send_to_backend(backend_name=connection.backend.name,
                               id_=out_msg.id,
                               text=out_msg.text,
                               identities=[connection.identity],
                               context=out_msg.fields)
        return out_msg
    return None
