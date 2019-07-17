from uuid import uuid4

from django.conf import settings

from register.tests.base import LibyaRapidTest
from register.models import SMS


class MessageUUID(LibyaRapidTest):
    def setUp(self):
        self.uuid = uuid4().hex
        self.conn = self.create_connection()

    def test_incoming_message(self):
        # all incoming messages should be accounted for in our DB
        self.receive("incoming", self.conn, fields={'external_id': self.uuid,
                                                    'to_addr': settings.REGISTRATION_SHORT_CODE})
        # a SMS should be created in our SMS table
        sms = SMS.objects.order_by('creation_date')[0]
        # the uuid for the sms, should be the same as the one vumi used
        self.assertEqual(sms.uuid, self.uuid)

    def test_outgoing_message(self):
        # all outgoing messages should be accounted for in our DB
        self.send("outgoing", self.conn)
        sms = SMS.objects.order_by('creation_date')[0]
        self.assertEqual(1, len(self.outbound))
        outgoing = self.outbound[0]
        # the uuid for the sms should be equal to the uuid from the outgoing msg
        self.assertEqual(sms.uuid, outgoing.id)
