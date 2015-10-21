from django.test import TestCase
from django.utils.translation import override

from text_messages.models import MessageText
from text_messages.utils import get_message, pick_text


class TextMessagesUtilsTestCase(TestCase):
    def setUp(self):
        self.number = 397
        self.msg = MessageText.objects.create(
            number=self.number,
            msg_en="Message",
            msg_ar="Message (ar)"
        )

    def test_get_message_success(self):
        msg = get_message(self.number)
        self.assertEqual(msg.pk, self.msg.pk)

    def test_get_message_nonesuch(self):
        with self.assertRaises(ValueError):
            get_message(self.number + 1)

    def test_pick_text_en(self):
        with override(language='en'):
            self.assertEqual('eng', pick_text('eng', 'ar'))

    def test_pick_text_not_en(self):
        with override(language='fr'):
            self.assertEqual('ar', pick_text('eng', 'ar'))

    def test_messages_are_cached(self):
        with self.assertNumQueries(1):
            get_message(self.number)
        with self.assertNumQueries(0):
            get_message(self.number)
        # If we save a message, the cache should be cleared and we
        # will have to query again
        MessageText.objects.get(number=self.number).save()
        with self.assertNumQueries(1):
            get_message(self.number)
        with self.assertNumQueries(0):
            get_message(self.number)

    def test_cache_clearing(self):
        # we can add, change, and delete messages and we keep
        # getting the right answers, despite the cache
        MessageText.objects.filter(pk=self.number).delete()
        with self.assertRaises(ValueError):
            get_message(self.number)
        new_number = self.number + 1
        with self.assertRaises(ValueError):
            get_message(new_number)
        msg = MessageText.objects.create(
            number=new_number,
            msg_en="new Message",
            msg_ar="new Message (ar)"
        )
        self.assertEqual("new Message", get_message(new_number).msg)
        msg.msg_en = "Newer message"
        msg.save()
        self.assertEqual("Newer message", get_message(new_number).msg)
