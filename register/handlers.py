import logging

from django.conf import settings
from django.utils import translation

from rapidsms.contrib.handlers import PatternHandler

from libya_elections import constants
from libya_elections.constants import RESPONSE_SERVER_ERROR
from .models import SMS
from .processors import process_registration_lookup, process_registration_request, Result
from .utils import is_blacklisted, is_whitelisted, registration_allowed


logger = logging.getLogger(__name__)


class LibyaHandlerMixin(object):
    """
    Some useful methods to mix into our handler classes.
    """

    @classmethod
    def send_response(cls, msg, message_code, **context):
        """
        Send a text message as a response to a message we've received.

        :param msg: A RapidSMS IncomingMessage to send a response to
        :param message_code: Our internal message code for the message to send
        :param context: Any parameters we need to format into the message before sending it
        :return:
        """
        result = Result(msg.fields.get('from_addr'), message_code, context)
        msg.respond(result.message, fields={'message_code': message_code})
        msg.sms.save()
        return True

    @classmethod
    def message_matches(cls, msg, regex):
        """
        Check if the text in the message matches the regex.
        If not, return `None`.
        If so, return an iterable of strings with the matched group results.

        :param msg: A RapidSMS IncomingMessage
        :param regex: A re.regex object
        :return: None, or a list of the matched groups (could be empty, depending
                on the regex)
        """
        m = regex.match(msg.text)
        if m:
            return m.groups()
        return None

    @classmethod
    def is_addressed_to_us(cls, msg):
        """Return True if the message was addressed to one of our
        acceptable_to_numbers.  (Must be set as a class attribute of
        any subclass.)"""
        return msg.fields.get('to_addr') in cls.acceptable_to_numbers

    @classmethod
    def is_whitelisted(cls, msg):
        """Return True if the message is from a whitelisted number."""
        return is_whitelisted(msg.fields.get('from_addr'))

    @classmethod
    def is_blacklisted(cls, msg):
        """Return True if the message is from a blacklisted number."""
        return is_blacklisted(msg.fields.get('from_addr'))


class LibyaHandler(LibyaHandlerMixin, PatternHandler):
    @classmethod
    def dispatch(cls, router, msg):
        # Always set the desired language context
        with translation.override(settings.OUTGOING_MESSAGE_LANGUAGE):
            handled = False
            try:
                # Possibly handle the message
                handled = super(LibyaHandler, cls).dispatch(router, msg)
            except Exception:
                # LOG ANY EXCEPTION THAT BUBBLES UP HERE
                logger.exception("An unexpected exception happened in "
                                 "%s.dispatch" % cls.__name__)
                if not msg.responses:
                    # We did not manage to send any response.  Send SOMETHING.
                    cls.send_response(msg, RESPONSE_SERVER_ERROR)
                msg.sms.save()
                # We handled it, return True
                return True
            else:
                # Save the SMS if we handled the message and it hasn't been saved
                if handled and not msg.sms.pk:
                    msg.sms.save()
                # We might not have handled it, but there was no exception. Let
                # other handlers try it.
                return handled

    def respond(self, text, **kwargs):
        # Force translation of response message to happen while we still have
        # the right language set.
        return self.msg.respond(unicode(text), **kwargs)

    def error(self, message_code):
        """Helper for handlers to respond with a particular message code."""
        result = Result(self.msg.sms.from_number, message_code)
        self.respond(result.message, fields={'message_code': result.message_code})


class VoterQueryHandler(LibyaHandler):
    # This comes before Tool_1_Handler in the list of handlers.
    # It allows voters to look up their registration at any time.
    acceptable_to_numbers = [
        settings.VOTER_QUERY_SHORT_CODE,
        settings.LIBYA_COUNTRY_CODE + settings.VOTER_QUERY_SHORT_CODE
    ]

    @classmethod
    def dispatch(cls, router, msg):
        # Only accept queries if message is addressed to this app
        if cls.is_addressed_to_us(msg):
            # First make sure the number is not blacklisted
            if cls.is_blacklisted(msg):
                result = Result(msg.fields.get('from_addr'), constants.BLACKLISTED_NUMBER)
                msg.respond(result.message, fields={'message_code': result.message_code})
                msg.sms.save()
                return True  # to stop further processing

            return super(VoterQueryHandler, cls).dispatch(router, msg)


class VoterQueryCitizenLookupHandler(VoterQueryHandler):
    """
    When a citizen sends in a query about their registration, respond with
    a message telling them their registration status.
    """
    pattern = r'^(\d{%d})$' % (constants.NID_LENGTH, )
    # NID is the right length.

    def handle(self, nid):
        logger.debug("VoterQueryCitizenLookupHandler")
        nid = long(nid)
        self.msg.sms.msg_type = SMS.QUERY
        self.msg.sms.save()
        result = process_registration_lookup(nid, self.msg.sms)
        self.respond(result.message, fields={'message_code': result.message_code})


class VoterQueryWrongLengthNIDHandler(VoterQueryHandler):
    """
    Return error message if the supplied voter query NID is of the incorrect length.
    """
    # This must come AFTER the handler for the right length NID in the handler list
    pattern = r'^(\d+)$'
    # NID is not the right length.

    def handle(self, nid):
        logger.debug("VoterQueryWrongLengthNIDHandler")
        self.msg.sms.msg_type = SMS.INVALID_NID_LENGTH
        self.msg.sms.save()
        logger.debug("msg = %s" % constants.VOTER_QUERY_NID_WRONG_LENGTH)
        self.error(constants.VOTER_QUERY_NID_WRONG_LENGTH)


# Tool 1 is SMS Voter Registration
class Tool_1_Handler(LibyaHandler):
    """
    Check 'to_addr' to verify that message was sent to REGISTRATION_SHORT_CODE
    -> If not, return False and lets another handler handle the message.
    -> If yes, then check that 'from_addr' is not blacklisted.
    -> If yes, return a blacklist message.
    -> If not, check if we're in the registration period.
    -> If not, return a 'we are closed' message
    -> If yes, dispatch the message for further processing in this app.
    """
    acceptable_to_numbers = [
        settings.REGISTRATION_SHORT_CODE,
        settings.LIBYA_COUNTRY_CODE + settings.REGISTRATION_SHORT_CODE
    ]

    @classmethod
    def dispatch(cls, router, msg):
        if not cls.is_addressed_to_us(msg):
            return False

        if cls.is_blacklisted(msg):
            result = Result(msg.fields.get('from_addr'), constants.BLACKLISTED_NUMBER)
            msg.respond(result.message, fields={'message_code': result.message_code})
            msg.sms.save()
            return True  # to stop further processing

        # Only accept registration if registration is open
        if not registration_allowed(msg):
            with translation.override(settings.OUTGOING_MESSAGE_LANGUAGE):
                # Registration is not open, respond and say so.
                result = Result(msg.fields.get('from_addr'), constants.REGISTRATION_NOT_OPEN)
                msg.respond(result.message, fields={'message_code': result.message_code})
                msg.sms.save()
                # Message has been handled.
            return True

        # Possibly handle the message
        return super(Tool_1_Handler, cls).dispatch(router, msg)


class RegistrationMessageHandler(Tool_1_Handler):
    """
    When a user sends in a syntactically valid registration message,
    process it and respond with the result.
    """

    pattern = r'^(\d{%d})\*(\d{%d})$' % (constants.NID_LENGTH, constants.CENTER_ID_LENGTH,)

    def handle(self, nid, center_id):
        logger.debug("RegistrationMessageHandler")
        center_id = int(center_id)
        nid = long(nid)
        self.msg.sms.msg_type = SMS.REGISTRATION
        result = process_registration_request(
            center_id, nid, self.msg.sms
        )
        self.respond(result.message, fields={'message_code': result.message_code})


class WrongNIDLengthHandler(Tool_1_Handler):
    pattern = r'^(\d+)\*(\d{%d})$' % (constants.CENTER_ID_LENGTH,)
    # Center ID is the right length, but we didn't match the registration message
    # pattern, so the NID must be the wrong length.

    def handle(self, nid, center_id):
        logger.debug("WrongNIDLengthHandler")
        self.msg.sms.msg_type = SMS.INVALID_NID_LENGTH
        self.error(constants.RESPONSE_NID_WRONG_LENGTH)


class WrongCenterIDLengthHandler(Tool_1_Handler):
    pattern = r'^(\d{%d})\*(\d+)$' % (constants.NID_LENGTH,)
    # NID is the right length, but we didn't match the registration message
    # pattern, so the center must be the wrong length.

    def handle(self, nid, center_id):
        logger.debug("WrongCenterIDLengthHandler")
        self.msg.sms.msg_type = SMS.INVALID_CENTRE_CODE_LENGTH
        logger.debug("msg = %s" % constants.RESPONSE_CENTER_ID_WRONG_LENGTH)
        self.error(constants.RESPONSE_CENTER_ID_WRONG_LENGTH)


class DefaultHandler(Tool_1_Handler):
    pattern = r'.*'

    def handle(self):
        logger.debug("DefaultHandler")
        self.msg.sms.msg_type = SMS.INVALID_FORMAT
        self.error(constants.MESSAGE_INCORRECT)
