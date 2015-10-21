import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test.utils import override_settings

from bulk_sms.models import Batch, BulkMessage
from bulk_sms.tests.factories import BatchFactory, BulkMessageFactory
from libya_elections.utils import get_random_number_string
from register.tests.base import LibyaTest


class BatchTest(LibyaTest):
    def test_unicode_method(self):
        batch = BatchFactory(name=u'foo')
        self.assertEqual(str(batch), u'foo')

    def test_active_batches(self):
        BatchFactory(status=Batch.PENDING, deleted=True)
        batch = BatchFactory(status=Batch.PENDING)
        self.assertEqual(Batch.objects.get_next_batch(), None)
        batch.status = Batch.APPROVED
        batch.save()
        self.assertEqual(Batch.objects.get_next_batch(), batch)
        batch.status = Batch.REJECTED
        batch.save()
        self.assertEqual(Batch.objects.get_next_batch(), None)
        batch.status = Batch.COMPLETED
        batch.save()
        self.assertEqual(Batch.objects.get_next_batch(), None)

    def test_multiple_active_batches(self):
        # Our code should use the highest priority batch
        batch1 = BatchFactory(status=Batch.APPROVED, priority=5)
        batch2 = BatchFactory(status=Batch.APPROVED, priority=2)
        BatchFactory(status=Batch.PENDING, deleted=True)
        self.assertEqual(Batch.objects.get_next_batch(), batch1)
        # dealing with batch1 will then make batch2 the highest priority one
        batch1.status = Batch.REJECTED
        batch1.save()
        self.assertEqual(Batch.objects.get_next_batch(), batch2)

    def test_get_random_messages_from_batch(self):
        batch = BatchFactory(status=Batch.PENDING)
        BatchFactory(status=Batch.PENDING, deleted=True)
        msgs = [BulkMessageFactory(batch=batch, sms=None) for i in range(10)]
        # the random message is one of our messages
        first_random_msg = batch.random_n_messages(n=1)[0]
        self.assertIn(first_random_msg, msgs)
        # get random message up to 10 times: shouldn't all be the same
        for i in range(10):
            next_random_msg = batch.random_n_messages(n=1)[0]
            if first_random_msg != next_random_msg:
                break
        self.assertNotEqual(first_random_msg, next_random_msg)
        # if we ask for more than exist, we only get the number that actually exist
        self.assertTrue(len(batch.random_n_messages(n=20)), 10)

    @override_settings(BULKSMS_DEFAULT_MESSAGES_PER_SECOND=2)
    def test_time_remaining(self):
        batch = BatchFactory(status=Batch.PENDING)
        [BulkMessageFactory(deleted=True, batch=batch, sms=None) for i in range(5)]
        msgs = [BulkMessageFactory(batch=batch, sms=None) for i in range(10)]
        self.assertEqual(batch.time_remaining(), datetime.timedelta(seconds=len(msgs) / 2))

    def test_time_remaining_one_message(self):
        # if there are any messages at all, should still return a True value for the template
        batch = BatchFactory(status=Batch.PENDING)
        BulkMessageFactory(batch=batch, sms=None)
        # using assertTrue because the key is that we want the return value to be boolean True
        # for the template to NOT display the 'Finished' default
        self.assertTrue(batch.time_remaining())

    def test_time_remaining_zero_messages(self):
        batch = BatchFactory(status=Batch.PENDING)
        self.assertEqual(batch.time_remaining(), 0)

    def test_add_messages_to_batch(self):
        batch = BatchFactory()
        msg = 'this is my message'
        shortcode = None
        gen = [("1", msg, shortcode), ("2", msg, shortcode), ("3", msg, shortcode)]
        batch.add_messages(gen)
        self.assertEqual(3, batch.messages.all().count())
        for message in batch.messages.all():
            self.assertEqual(msg, message.message)
            # from_shortcode should get set to default value (REGISTRATION_SHORT_CODE)
            self.assertEqual(settings.REGISTRATION_SHORT_CODE, message.from_shortcode)


class BulkMessageTest(LibyaTest):
    def test_unicode_method(self):
        msg = BulkMessageFactory(phone_number=u'555-1212')
        self.assertIn('555-1212', str(msg))

    def test_active(self):
        msg1 = BulkMessageFactory(phone_number=u'555-1212', deleted=True)
        msg2 = BulkMessageFactory(phone_number=u'555-1212', batch=msg1.batch)
        BulkMessageFactory(phone_number=u'555-1212')
        # ensure the manager method works
        self.assertEqual(BulkMessage.objects.active().count(), 2)
        # ensure the queryset method works on a filtered queryset
        self.assertEqual(BulkMessage.objects.filter(batch=msg2.batch).active().count(), 1)

    def test_sent(self):
        msg1 = BulkMessageFactory(phone_number=u'555-1212')
        BulkMessageFactory(phone_number=u'555-1212')
        # ensure the manager method works
        self.assertEqual(BulkMessage.objects.sent().count(), 2)
        # ensure the queryset method works on a filtered queryset
        self.assertEqual(BulkMessage.objects.filter(batch=msg1.batch).sent().count(), 1)

    def test_unsent(self):
        msg1 = BulkMessageFactory(phone_number=u'555-1212', sms=None)
        BulkMessageFactory(phone_number=u'555-1212', sms=None)
        # ensure the manager method works
        self.assertEqual(BulkMessage.objects.unsent().count(), 2)
        # ensure the queryset method works on a filtered queryset
        self.assertEqual(BulkMessage.objects.filter(batch=msg1.batch).unsent().count(), 1)

    def test_from_shortcode_default(self):
        msg = BulkMessageFactory()
        self.assertEqual(msg.from_shortcode, settings.REGISTRATION_SHORT_CODE)

    def test_from_shortcode_validation(self):
        msg = BulkMessageFactory()
        msg.from_shortcode = get_random_number_string(length=5)
        with self.assertRaisesRegexp(ValidationError, 'Invalid shortcode'):
            msg.full_clean()
