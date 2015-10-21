# -*- coding: utf-8 -*-
import os
import signal
import threading
import multiprocessing
from unittest import skipIf

from django.test import TestCase, TransactionTestCase
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.db import connections as django_db_connections

from django_nose.runner import _reusing_db
from mock import patch
from rapidsms.models import Connection
from rapidsms.tests.harness import backend, router, TestRouter
from rapidsms.errors import MessageSendingError

from bulk_sms.models import Batch, BulkMessage
from bulk_sms.sending import send_messages, send_message_by_id, MessageSendingLoop
from bulk_sms.tests.factories import BulkMessageFactory, BatchFactory
from libya_elections.utils import get_random_number_string
from register.tests.factories import ConnectionFactory, SMSFactory


# Override some of the RapidSMS test infrastructure since we're
# sending messages at a lower level than the test infrastructure expects
class LowLevelTestRouter(TestRouter):
    def __init__(self, *args, **kwargs):
        super(LowLevelTestRouter, self).__init__(*args, **kwargs)
        if kwargs.pop('use_multiprocessing', False):
            # use multiprocessing-safe list for sharing outbound messages across
            # processes
            self.outbound = multiprocessing.Manager().list()

    def send_to_backend(self, backend_name, id_, text, identities, context):
        """Save all outbound messages locally for test inspection"""
        self.outbound.append(text)
        super(LowLevelTestRouter, self).send_to_backend(
            backend_name, id_, text, identities, context)


class LowLevelRouterMixin(router.CustomRouterMixin):
    backends = {'almadar': {'ENGINE': backend.MockBackend},
                'libyana': {'ENGINE': backend.MockBackend}}

    def set_router(self, use_multiprocessing=False):
        self.router = LowLevelTestRouter(backends=self.backends,
                                         use_multiprocessing=use_multiprocessing)
        self.router_class = self.router
        super(LowLevelRouterMixin, self).set_router()

    @property
    def outbound(self):
        """The list of message objects sent by the router."""
        return self.router.outbound


class MultiprocessingLowLevelRouterMixin(LowLevelRouterMixin):

    def set_router(self):
        super(MultiprocessingLowLevelRouterMixin, self).set_router(use_multiprocessing=True)


class SignalHandlerTest(TestCase):
    def setUp(self):
        self.loop = MessageSendingLoop()

    def test_signal_handler_installation_removal(self):
        """
        Make sure we can install and remove signal handlers, and that they get
        updated appropriately.
        """
        saved = dict([(s, signal.getsignal(s)) for s in self.loop.signals])
        self.loop._install_signal_handlers()
        for sig in self.loop.signals:
            self.assertEqual(signal.getsignal(sig), self.loop._signal_handler)
        self.loop._restore_signal_handlers()
        for sig in self.loop.signals:
            self.assertEqual(signal.getsignal(sig), saved[sig])

    def test_signal_handler_parent_proc(self):
        """
        Test signal as if it arrived in the parent process.
        """
        self.loop._running = True
        self.loop._signal_handler(signal.SIGHUP, None)
        self.assertFalse(self.loop._running)
        # make sure running again doesn't raise an error
        self.loop._signal_handler(signal.SIGHUP, None)

    def test_signal_handler_child_proc_ignored(self):
        """
        Test signal as if it arrived in a child process.
        """
        self.loop._parent_pid = os.getpid() + 1  # anything other than os.getpid()
        self.loop._running = True
        self.loop._signal_handler(signal.SIGHUP, None)
        self.assertTrue(self.loop._running)


class SendingTest(LowLevelRouterMixin, TestCase):
    def setUp(self):
        # create an approved Batch
        self.batch = BatchFactory(status=Batch.APPROVED)
        # add message to batch
        self.bulk_msg = BulkMessageFactory(
            batch=self.batch,
            phone_number=get_random_number_string(),
            message=u'.نآسف، مرحلة التسجيل عن طريق الرسائل النصية ليست متاحة',
            sms=None
        )

    def test_send_one_bulk_message(self):
        # send message
        send_message_by_id(self.bulk_msg.pk)
        # -> sms is no longer 'None'
        sms = BulkMessage.objects.get(id=self.bulk_msg.id).sms
        self.assertTrue(sms)
        # -> from_number is REGISTRATION_SHORT_CODE (default)
        self.assertEqual(sms.from_number, settings.REGISTRATION_SHORT_CODE)
        # -> to_number is the phone number from the BulkMessage
        self.assertEqual(sms.to_number, self.bulk_msg.phone_number)
        # -> message is the message from the BulkMessage
        self.assertEqual(sms.message, self.bulk_msg.message)
        self.assertEqual(len(self.outbound), 1)

    @patch.object(LowLevelTestRouter, 'send_to_backend')
    def test_endpoint_is_passed_to_backend(self, mock_send_to_backend):
        # mock sending the message to check what params we send to the backend
        send_message_by_id(self.bulk_msg.pk)
        self.assertTrue(mock_send_to_backend.called)
        call_args, call_kwargs = mock_send_to_backend.call_args
        # by default, we should send endpoint=REGISTRATION_SHORT_CODE
        self.assertEqual(call_kwargs['context'], {'endpoint': settings.REGISTRATION_SHORT_CODE})

    def test_endpoint_passed_to_backend_is_customizable(self):
        self.bulk_msg.from_shortcode = settings.REPORTS_SHORT_CODE
        self.bulk_msg.save()
        # send message
        with patch.object(LowLevelTestRouter, 'send_to_backend') as mock_send_to_backend:
            send_message_by_id(self.bulk_msg.pk)
        self.assertTrue(mock_send_to_backend.called)
        call_args, call_kwargs = mock_send_to_backend.call_args
        self.assertEqual(call_kwargs['context'], {'endpoint': settings.REPORTS_SHORT_CODE})

    def test_endpoint_gets_saved_to_sms_object(self):
        self.bulk_msg.from_shortcode = settings.REPORTS_SHORT_CODE
        self.bulk_msg.save()
        # send message
        send_message_by_id(self.bulk_msg.pk)
        sms = BulkMessage.objects.get(id=self.bulk_msg.id).sms
        self.assertEqual(sms.from_number, settings.REPORTS_SHORT_CODE)

    def test_dont_send_msg_if_sms_field_set(self):
        # set the sms field
        self.bulk_msg.sms = SMSFactory()
        self.bulk_msg.save()
        send_message_by_id(self.bulk_msg.pk)
        # no message sent
        self.assertEqual(len(self.outbound), 0)

    def test_dont_send_msg_if_batch_inactive(self):
        self.batch.status = Batch.PENDING
        self.batch.save()
        send_message_by_id(self.bulk_msg.pk)
        # no message sent
        self.assertEqual(len(self.outbound), 0)

    def test_bulk_sms_send_one_proc(self):
        for i in range(30):
            BulkMessageFactory(batch=self.batch, sms=None)
        for j in range(10):
            BulkMessageFactory(batch=self.batch, sms=None, deleted=True)
        num_sent = send_messages(self.batch)
        # 31 messages sent (30 + 1 from setUp)
        self.assertEqual(len(self.outbound), 31)
        # assert that we report the right number sent too
        self.assertEqual(num_sent, 31)

    def test_sent_messages_dont_get_resent(self):
        for i in range(20):
            BulkMessageFactory(batch=self.batch, sms=None)
        for i in range(10):
            sms = SMSFactory()
            BulkMessageFactory(batch=self.batch, sms=sms)
            BulkMessageFactory(batch=self.batch, sms=SMSFactory(), deleted=True)
        send_messages(self.batch)
        # only 21 messages get sent out (20 + 1 from setUp)
        self.assertEqual(len(self.outbound), 21)

    def test_send_finite_number_each_time(self):
        for i in range(20):
            BulkMessageFactory(batch=self.batch, sms=None)
        send_messages(self.batch, num_to_send=10)
        # only 10 messages should be sent out each call
        self.assertEqual(len(self.outbound), 10)

    def test_once_all_are_sent_next_send_completes_batch(self):
        for i in range(20):
            BulkMessageFactory(batch=self.batch, sms=None)
        BulkMessageFactory(batch=self.batch, sms=None, deleted=True)
        # send out all the messages (21)
        send_messages(self.batch)
        self.assertEqual(len(self.outbound), 21)
        # send again
        BulkMessageFactory(batch=self.batch, sms=None, deleted=True)
        send_messages(self.batch)
        # now batch should be completed
        batch = Batch.objects.get(pk=self.batch.pk)
        self.assertEqual(batch.status, Batch.COMPLETED)

    def test_dont_send_batch_if_batch_inactive(self):
        self.batch.status = Batch.PENDING
        self.batch.save()
        send_messages(self.batch)
        # no message sent
        self.assertEqual(len(self.outbound), 0)

    @patch('bulk_sms.sending.get_router', autospec=True)
    def test_if_message_fails_error_incremented(self, mock_get_router):
        self.assertEqual(self.batch.errors, 0)
        # send the message, mocking an exception
        mock_get_router.return_value.send_to_backend.side_effect = MessageSendingError
        send_messages(self.batch)
        batch = Batch.objects.get(pk=self.batch.pk)
        self.assertEqual(batch.errors, 1)
        self.assertFalse(self.bulk_msg.sms)

    def test_send_to_invalid_id(self):
        """
        Ensure sending to an invalid ID returns gracefully
        """
        self.assertEqual(send_message_by_id(9999999), 0)

    @patch.object(LowLevelTestRouter, 'send_to_backend')
    def test_send_to_existing_connection(self, send_to_backend):
        """
        Ensure bulk messages to phone numbers with existing connections use that
        connection. This helps ensure (but does not guarantee) that messages to
        Thuraya phones won't be sent over Madar or Libyana.
        """
        # use a backend that's available in the test environment but not
        # in BULKSMS_BACKENDS
        conn = ConnectionFactory(identity=self.bulk_msg.phone_number,
                                 backend__name=settings.HTTPTESTER_BACKEND)
        old_count = Connection.objects.all().count()
        # send message
        send_message_by_id(self.bulk_msg.pk)
        # make sure send_to_backend was called with the correct backend name and
        # identity
        self.assertEqual(send_to_backend.call_count, 1)
        self.assertEqual(send_to_backend.call_args[1]['backend_name'], conn.backend.name)
        self.assertEqual(send_to_backend.call_args[1]['identities'], [conn.identity])
        # make sure no new connection object was created:
        new_count = Connection.objects.all().count()
        self.assertEqual(old_count, new_count)


# must use TransactionTestCase because sending is done in multiple threads,
# which all need to access the database simultaneously
# skip when reusing DB until https://code.djangoproject.com/ticket/23727 is fixed
@skipIf(_reusing_db(), "until https://code.djangoproject.com/ticket/23727 is fixed")
class ThreadedSendingTest(LowLevelRouterMixin, TransactionTestCase):
    # https://docs.djangoproject.com/en/1.7/topics/testing/tools/#transactiontestcase
    # See the first warning, also read the comment here:
    # https://github.com/django/django/blob/b626c289ccf9cc487f97d91c2a45cac096d9d0c7/django/test/testcases.py#L734

    # UNCOMMENT once https://code.djangoproject.com/ticket/23727 is fixed
    # so we can remove the @skipIf above
    # serialized_rollback = True

    def setUp(self):
        # create an approved Batch
        self.batch = BatchFactory(status=Batch.APPROVED)

    def test_send_is_threadsafe(self):
        """
        Ensure send_message_by_id does not accidentally send more than one
        SMS to the same user if it happens to be running more than once with the
        same ID.
        """
        trigger = threading.Event()

        def target(pk):
            # wait until all threads have started before attempting to send
            trigger.wait()
            send_message_by_id(pk)
            # workaround https://code.djangoproject.com/ticket/22420
            for conn in django_db_connections.all():
                conn.close()
        m = BulkMessageFactory(batch=self.batch, sms=None)
        threads = [threading.Thread(target=target, args=(m.pk,))
                   for i in range(10)]
        for t in threads:
            t.start()
        # wake up all threads at the same time
        trigger.set()
        for t in threads:
            t.join()
        # only 1 message should be sent out in total
        self.assertEqual(len(self.outbound), 1)


# use TransactionTestCase plus router mixin to ensure multiprocessing-safe
# saving of outbound messages during tests
# skip when reusing DB until https://code.djangoproject.com/ticket/23727 is fixed
@skipIf(_reusing_db(), "until https://code.djangoproject.com/ticket/23727 is fixed")
class MultiprocSendingTest(MultiprocessingLowLevelRouterMixin, TransactionTestCase):
    # https://docs.djangoproject.com/en/1.7/topics/testing/tools/#transactiontestcase
    # See the first warning, also read the comment here:
    # https://github.com/django/django/blob/b626c289ccf9cc487f97d91c2a45cac096d9d0c7/django/test/testcases.py#L734

    # UNCOMMENT once https://code.djangoproject.com/ticket/23727 is fixed
    # so we can remove the @skipIf above
    # serialized_rollback = True

    def setUp(self):
        # create an approved Batch
        self.batch = BatchFactory(status=Batch.APPROVED)

    def test_cache_is_working(self):
        # If cache isn't working, other tests are not really valid
        if cache.get('CACHETEST', default=False):
            cache.delete('CACHETEST')
        self.assertTrue(cache.add('CACHETEST', True),
                        msg="cache.add returned failure. "
                            "Is cache configured and working correctly?")
        self.assertTrue(cache.get('CACHETEST', default=False),
                        msg="cache.get did not returned the value we cached. "
                            "Is cache configured and working correctly?")
        cache.delete('CACHETEST')

    def test_bulk_sms_send_multiproc(self):
        # close database connections manually to make sure they're not passed
        # to subprocesses
        for conn in django_db_connections.all():
            conn.close()
        # send the messages in parallel using 10 processes. use
        # multiprocessing rather than threads so we don't have to clean
        # up database connections that the threads might leave open.
        cache.close()
        pool = multiprocessing.Pool(10)
        try:
            for i in range(30):
                BulkMessageFactory(batch=self.batch, sms=None)
            for j in range(10):
                BulkMessageFactory(batch=self.batch, sms=None, deleted=True)
            # 40 is the first multiple of 10 greater than or equal to 31
            num_sent = send_messages(self.batch, num_to_send=40, map_=pool.map)
            batch = Batch.objects.get(pk=self.batch.pk)
            self.assertEqual(batch.errors, 0)
            self.assertEqual(batch.status, Batch.COMPLETED)
            # assert that we report the right number sent too
            self.assertEqual(num_sent, 30)
            self.assertEqual(len(self.outbound), 30)
        finally:
            pool.terminate()
            pool.join()

    def test_management_cmd(self):
        # Make sure the bulk sending management command works (for a single batch, at least).
        for i in range(50):
            BulkMessageFactory(batch=self.batch, sms=None)
        call_command('send_bulk_messages', concurrent_workers=10, msgs_per_sec=50,
                     send_forever=False)
        batch = Batch.objects.get(pk=self.batch.pk)
        self.assertEqual(batch.errors, 0)
        self.assertEqual(batch.status, Batch.COMPLETED)
        self.assertEqual(len(self.outbound), 50)
