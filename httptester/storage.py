""" Store and get messages from cache """

from django.conf import settings

from rapidsms.backends.database.models import INCOMING, BackendMessage
from rapidsms.router import receive, lookup_connections


BACKEND_NAME = settings.HTTPTESTER_BACKEND


def get_messages():
    """Return a queryset with the message data"""
    return BackendMessage.objects.filter(name=BACKEND_NAME)


def store_message(direction, identity, text):
    """

    :param direction: "in" or "out" depending on whether the message
       was sent to (into) RapidSMS, or out of RapidSMS.
    :param identity: Phone number the message was sent from (in)
       or to (out)
    :param text: The message
    """
    BackendMessage.objects.create(direction=direction, identity=identity,
                                  text=text, name=BACKEND_NAME)


def store_and_queue(identity, text, to_addr=None):
    """Store a message in our log and send it into RapidSMS.

    :param identity: Phone number the message will appear to come from
    :param text: The message text
    :param to_addr: Phone number that the message is sent to
    """
    store_message(INCOMING, identity, text)
    connection = lookup_connections(BACKEND_NAME, [identity])[0]
    receive(text, connection, fields={'to_addr': to_addr, 'from_addr': identity})


def clear_messages(identity):
    """Forget messages to/from this identity

    :param identity: The phone number whose messages will be cleared
    """
    BackendMessage.objects.filter(identity=identity,
                                  name=BACKEND_NAME).delete()


def clear_all_messages():
    """Forget all messages"""
    BackendMessage.objects.filter(name=BACKEND_NAME).delete()
