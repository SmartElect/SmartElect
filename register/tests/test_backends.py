from unittest.mock import patch

from rapidsms.errors import MessageSendingError

from register.backends import WhitelistedVumiBackend
from register.tests.base import LibyaRapidTest
from register.tests.factories import WhitelistFactory


class TestWhitelistedVumiBackend(LibyaRapidTest):

    def setUp(self):
        # create a message, and extract the phone_number
        self.message = self.create_outgoing_message()
        self.phone_number = self.message.connections[0].identity
        # create the backend
        config = {"sendsms_url": "http://example.com"}
        self.backend = WhitelistedVumiBackend(None, "vumi", **config)

    def test_phone_number_not_whitelisted(self):
        "Non-whitelisted phone number should raise error."
        with self.assertRaises(MessageSendingError) as ctx:
            self.backend.send(self.message.id, self.message.text, [self.phone_number], {})
        self.assertIn('numbers are not whitelisted', str(ctx.exception))
        self.assertIn(self.phone_number, str(ctx.exception))

    def test_phone_number_whitelisted(self):
        "Whitelisted phone number should succeed."
        WhitelistFactory(phone_number=self.phone_number)
        with patch('rapidsms.backends.vumi.outgoing.requests.post'):
            self.backend.send(self.message.id, self.message.text, [self.phone_number], {})

    def test_mix_of_whitelisted_and_not_whitelisted(self):
        """
        Any non-whitelisted phone number should raise error, even if some of the
        numbers in the list are whitelisted.
        """
        whitelisted_number = WhitelistFactory().phone_number
        phone_numbers = [self.phone_number, whitelisted_number]
        with self.assertRaises(MessageSendingError) as ctx:
            self.backend.send(self.message.id, self.message.text, phone_numbers, {})
        self.assertIn('numbers are not whitelisted', str(ctx.exception))
        self.assertIn(self.phone_number, str(ctx.exception))

    def test_duplicate_whitelisted_number(self):
        """
        A duplicate whitelisted number is OK.
        """
        WhitelistFactory(phone_number=self.phone_number)
        phone_numbers = [self.phone_number, self.phone_number]
        with patch('rapidsms.backends.vumi.outgoing.requests.post'):
            self.backend.send(self.message.id, self.message.text, phone_numbers, {})

    def test_duplicate_non_whitelisted_number(self):
        """
        A duplicate non-whitelisted number is not OK.
        """
        phone_numbers = [self.phone_number, self.phone_number]
        with self.assertRaises(MessageSendingError) as ctx:
            self.backend.send(self.message.id, self.message.text, phone_numbers, {})
        self.assertIn('numbers are not whitelisted', str(ctx.exception))
        self.assertIn(self.phone_number, str(ctx.exception))
