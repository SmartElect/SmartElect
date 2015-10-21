import logging
import string
import textwrap

from django.conf import settings
from django.views.decorators.debug import sensitive_variables

from rapidsms.apps.base import AppBase
from rapidsms.router import send
from libya_elections.constants import INCOMING, OUTGOING, PUNT

from libya_elections.utils import clean_input_msg

from .models import SMS
from .processors import Result

logger = logging.getLogger(__name__)


class PreprocessApp(AppBase):
    """The main point of this app is to make sure that we insert all messages
    that we send or receive into the SMS table.

    Incoming: During the parse phase, we also clean all input messages making it
              easier to match them in our pattern handlers
    Outgoing: During the outgoing phase, we split all messages over
              MAX_OUTGOING_LENGTH characters.
    """

    def parse(self, msg):
        # insert into SMS database, and add sms object to msg
        sms = SMS(
            from_number=msg.connections[0].identity,
            to_number=msg.fields.get('to_addr', settings.REGISTRATION_SHORT_CODE),
            uuid=msg.fields.get('external_id', ''),
            carrier=msg.connections[0].backend,
            msg_type=SMS.UNKNOWN,
            message=msg.raw_text,
            direction=INCOMING,
        )
        # WARNING: SMS not saved yet!  It must be saved during processing at some point
        msg.sms = sms
        # remove extraneous whitespace/characters, translate, and format nicely
        msg.text = clean_input_msg(msg.text)
        logger.debug("Raw -> Cleaned: %s -> %s" % (msg.raw_text, msg.text))

    def _split_and_send_messages(self, msg, msg_type):
        width = settings.MAX_OUTGOING_LENGTH - settings.MSG_ORDER_NUMBER_LENGTH
        short_msgs = textwrap.wrap(msg.raw_text, width=width)
        for i, short_msg in enumerate(short_msgs):
            # format the msg with a paginator syntax at end of msg
            short_text = u"[%d/%d] %s" % (i + 1, len(short_msgs), short_msg)
            # RapidSMS has a 'fields' kwarg for extra metadata
            # Keep track of the fact that this is a split message
            # Keep track of the sequence of this message
            # Keep track of the proper msg_type
            fields = {'split': True, 'order': i + 1, 'msg_type': msg_type}
            kwargs = {"fields": fields}
            if i == 0:
                kwargs['in_response_to'] = msg.in_response_to
            send(short_text, msg.connections, **kwargs)

    def _transform_msg_text(self, raw_text, transformation_dict=None):
        """
        Replace substrings in raw_text (based on the old/new pairs defined in
        transformation_dict) and return the result.

        Why is this method needed?
        Some phones autocorrect '8)' to a smiley face. As a workaround, we add a space
        between those two characters. We define any such changes in
        transformation_dict. It would be nicer to use something like \uFEFF which is a
        zero width non-breaking space, but tests have shown that the phones in question
        may display that incorrectly.

        Note that we leave raw_text unchanged, so that we can continue to use that
        in our automated tests when we need to test our responses, without our test
        suite having to know about this hack.
        """
        if not transformation_dict:
            transformation_dict = settings.OUTGOING_MSG_TRANSFORMATIONS
        result = raw_text
        for old, new in transformation_dict.iteritems():
            result = string.replace(result, old, new)
        return result

    @sensitive_variables('msg')
    def outgoing(self, msg):
        msg.text = self._transform_msg_text(msg.raw_text)

        message_code = getattr(msg, 'fields', {}).get('message_code', 0)
        if msg.in_response_to:
            in_response_to = msg.in_response_to.sms
            # respond from the number they sent their message to
            from_number = in_response_to.to_number
            # use same msg_type as the incoming message
            msg_type = in_response_to.msg_type
            # update the incoming message_code to match
            in_response_to.message_code = message_code
            in_response_to.save()
        else:
            msg_type = SMS.BULK_OUTGOING_MESSAGE
            from_number = msg.fields.get('endpoint', settings.REGISTRATION_SHORT_CODE)
            in_response_to = None

        # split long messages
        order = None
        if settings.SPLIT_LONG_MESSAGES:
            if len(msg.raw_text) > settings.MAX_OUTGOING_LENGTH:
                self._split_and_send_messages(msg, msg_type)
                # return False so we don't continue sending the long message
                return False
            if msg.fields.get('split'):
                logger.debug("Split message # %d" % msg.fields['order'])
                order = msg.fields['order']
                msg_type = msg.fields['msg_type']

        # create an SMS object for each connection
        for conn in msg.connections:
            # this will result in multiple sms messages having the same uuid :/
            # for our purposes, we should not have an instance where we have multiple
            # connections, and this should not be an issue.
            sms = SMS.objects.create(
                from_number=from_number,
                to_number=conn.identity,
                carrier=conn.backend,
                msg_type=msg_type,
                message=msg.raw_text,
                direction=OUTGOING,
                order=order,
                uuid=msg.id,
                message_code=message_code,
                in_response_to=in_response_to,
            )
            msg.sms = sms
        return True

    def default(self, msg):
        """
        This will ONLY be invoked if no application has handled
        the incoming message.
        """
        msg.sms.msg_type = SMS.NOT_HANDLED
        msg.sms.save()
        result = Result(msg.fields.get('from_addr'), PUNT)
        msg.respond(result.message)

        # Returning True will prevent any applications later in the
        # list from having their own default handlers invoked.
        return True
