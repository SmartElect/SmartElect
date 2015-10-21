from django.test import TestCase
from django.utils.translation import override
from text_messages.models import MessageText


class TextMessagesModelsTestCase(TestCase):
    def setUp(self):
        self.number = 397
        self.msg = MessageText.objects.create(
            number=self.number,
            msg_en="Message",
            msg_ar="Message (ar)",
            enhanced_en="Enh msg",
            enhanced_ar="Enh msg (ar)",
        )

    def test_msg_property_en(self):
        with override(language='en'):
            self.assertEqual('Message', self.msg.msg)

    def test_msg_property_ar(self):
        with override(language='ar'):
            self.assertEqual('Message (ar)', self.msg.msg)

    def test_enh_property_en(self):
        with override(language='en'):
            self.assertEqual('Enh msg', self.msg.enhanced)

    def test_enh_property_ar(self):
        with override(language='ar'):
            self.assertEqual('Enh msg (ar)', self.msg.enhanced)
