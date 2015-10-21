import datetime

from django.core.cache import cache
from django.test import TestCase
from django.utils import translation
from django.utils.timezone import now
from rapidsms.tests.harness import RapidTest

from register.tests.factories import BackendFactory, ConnectionFactory
from text_messages.utils import get_message


PAST_DAY = now() - datetime.timedelta(days=2)
FUTURE_DAY = now() + datetime.timedelta(days=2)


class LibyaTest(TestCase):
    def tearDown(self):
        cache.clear()


class LibyaRapidTest(RapidTest):
    def create_backend(self, data=None):
        if data is None:
            data = {}
        return BackendFactory(**data)

    def create_connection(self, data=None):
        if data is None:
            data = {}
        return ConnectionFactory(**data)

    def full_outbound(self):
        """
        Return all full outbound messages (stripping out our split responses)
        """
        # Our split messages are the only ones with a fields attribute
        return [o for o in self.outbound if not o.fields.get('split')]

    def get_last_response(self):
        """
        Return the last full SMS message (i.e. not a split message) we sent in response
        """
        return self.full_outbound()[-1]

    def get_last_response_code(self):
        """
        Return the `message_code` of the latest full SMS message (i.e. not a split message)
        we sent in response.
        """
        return self.get_last_response().fields['message_code']

    def get_all_response_codes(self):
        """
        Return the message codes from all the responses.
        """
        return [msg.fields['message_code'] for msg in self.full_outbound()]

    def get_last_response_message(self):
        """
        Return the `raw_text` of the latest full SMS message we sent in response.

        There are 2 different fields that contain message text. Our system generates a
        properly translated response and we store that in `raw_text`. Just before actually
        sending the message out to a phone, we might manipulate the text (in
        register.app._transform_msg_text). The result of those manipulations are stored in
        `text`. When testing whether our system is functioning as expected, we therefore
        test against `raw_text` and that is what this method returns. Methods that are
        specifically testing the outgoing text manipulation should test against
        `get_last_response().text`
        """
        return self.get_last_response().raw_text

    def tearDown(self):
        cache.clear()


class TranslationTest(object):
    @staticmethod
    def translate(message_code, context={}, language='ar', enhanced=False):
        with translation.override(language):
            if enhanced:
                text = get_message(message_code).enhanced
            else:
                text = get_message(message_code).msg
            return text.format(**context)
