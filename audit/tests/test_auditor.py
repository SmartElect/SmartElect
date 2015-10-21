from datetime import timedelta

from django.conf import settings
from django.core import mail
from django.test import TestCase
from django.utils.timezone import now

from audit import models
from audit.tasks import audit_sms, audit_incoming_sms, audit_outgoing_sms
from audit.tests.factories import VumiLogFactory
from libya_elections.constants import OUTGOING, INCOMING
from register.models import SMS
from register.tests.factories import BackendFactory, SMSFactory
from subscriptions.tests.factories import SubscriptionFactory


class AuditorMixin(object):
    @staticmethod
    def create_batch(factory, size, start=0, **kwargs):
        # returns a list of freshly created instances starting from the same uuid
        instances = []
        n = start + 1
        for iteration in range(start, start + size + 1):
            uuid = 'uuid-%s' % n
            kwargs.update(uuid=uuid)
            instances.append(factory.create(**kwargs))
            n += 1
        return instances


class IncomingMessageTest(AuditorMixin, TestCase):
    # all incoming messages in the vumi log match those in our SMS table
    def setUp(self):
        # create subscribers
        SubscriptionFactory.create_batch(size=3)
        # create a vumi backend
        self.vumi_backend = BackendFactory(name='vumi')
        # to add noise to the db
        self.create_batch(VumiLogFactory, 5, direction=OUTGOING, start=100)
        self.create_batch(SMSFactory, 3, direction=OUTGOING, start=100, carrier=self.vumi_backend)

    def no_discrepancies_test(self):
        # both of the incoming batches
        self.create_batch(VumiLogFactory, 5)
        self.create_batch(SMSFactory, 5, carrier=self.vumi_backend)
        audit_incoming_sms()
        discrepancies = models.Discrepancy.objects.all()
        self.assertEqual(discrepancies.count(), 0)

    def discrepancies_found_test(self):
        self.create_batch(VumiLogFactory, 6)
        self.create_batch(SMSFactory, 5, carrier=self.vumi_backend)
        audit_incoming_sms()
        discrepancies = models.Discrepancy.objects.all()
        self.assertEqual(discrepancies.count(), 1)


class OutgoingMessageTest(AuditorMixin, TestCase):
    # all outgoing messages in SMS table should match those in the vumi logs
    def setUp(self):
        # create subscribers
        SubscriptionFactory.create_batch(size=3)
        # create a vumi backend
        self.vumi_backend = BackendFactory(name='vumi')
        # to add noise to the db
        self.create_batch(VumiLogFactory, 5, direction=INCOMING, start=100)
        self.create_batch(SMSFactory, 2, direction=INCOMING, start=100, carrier=self.vumi_backend)

    def no_discrepancies_test(self):
        creation_date = now() - timedelta(hours=25)
        self.create_batch(VumiLogFactory, 5, direction=OUTGOING)
        self.create_batch(SMSFactory, 5, direction=OUTGOING, creation_date=creation_date,
                          carrier=self.vumi_backend)
        audit_outgoing_sms()
        discrepancies = models.Discrepancy.objects.all()
        self.assertEqual(discrepancies.count(), 0)

    def discrepancies_found_test(self):
        creation_date = now() - timedelta(hours=25)
        self.create_batch(VumiLogFactory, 5, direction=OUTGOING)
        self.create_batch(SMSFactory, 6, creation_date=creation_date,
                          direction=OUTGOING, carrier=self.vumi_backend)
        audit_outgoing_sms()
        discrepancies = models.Discrepancy.objects.all()
        self.assertEqual(discrepancies.count(), 1)

    def test_dont_find_message_tester_sms_objects(self):
        """SMS objects which don't go to Vumi should not be audited."""
        # make sure the SMS objects are older than 24 hours, or else we don't audit them
        creation_date = now() - timedelta(hours=25)
        # create a message_tester SMS object which should not get audited
        test_backend = BackendFactory(name=settings.HTTPTESTER_BACKEND)
        SMSFactory(direction=OUTGOING, creation_date=creation_date, carrier=test_backend)
        # create an SMS object that SHOULD get audited
        audited_sms = SMSFactory(direction=OUTGOING, creation_date=creation_date,
                                 carrier=self.vumi_backend)
        audit_outgoing_sms()
        discrepancies = models.Discrepancy.objects.all()
        # only 1 discrepancy found
        self.assertEqual(discrepancies.count(), 1)
        self.assertEqual(discrepancies[0].trail.sms, audited_sms)


class AuditSMSTest(AuditorMixin, TestCase):
    # all outgoing messages in SMS table should match those in the vumi logs
    def setUp(self):
        # create subscribers
        SubscriptionFactory.create_batch(size=3)
        # create a vumi backend
        self.vumi_backend = BackendFactory(name='vumi')
        # 3 incoming discrepancies
        incoming = INCOMING
        self.create_batch(VumiLogFactory, 5, direction=incoming)
        self.create_batch(SMSFactory, 2, direction=incoming, carrier=self.vumi_backend)
        # 2 outgoing discrepancies
        outgoing = OUTGOING
        creation_date = now() - timedelta(hours=25)
        self.create_batch(VumiLogFactory, 3, direction=outgoing, start=10)
        # sms are older than 24 hours
        self.create_batch(SMSFactory, 5, direction=outgoing,
                          creation_date=creation_date, start=10, carrier=self.vumi_backend)

    def audited_sms_test(self):
        # messages that created a discrepancy once will not create
        # a new one when the auditor is run again
        audit_sms.delay()
        discrepancies = models.Discrepancy.objects.all()
        self.assertEqual(discrepancies.count(), 5)
        # auditor second run
        audit_sms.delay()
        discrepancies = models.Discrepancy.objects.all()
        self.assertEqual(discrepancies.count(), 5)

    def notifications_sent_test(self):
        # subscribers should be notified about discrepancies
        audit_sms.delay()
        # discrepancies found (5)
        # send email to each of the 3 subscribers
        self.assertEqual(len(mail.outbox), 3)
        # auditor second run
        audit_sms.delay()
        # no new discrepancies found
        # no new emails added to the outbox
        self.assertEqual(len(mail.outbox), 3)

    def only_audit_old_sms_test(self):
        # mark all SMS and VumiLog instances in the db as audited
        models.VumiLog.objects.update(is_audited=True)
        SMS.objects.update(is_audited=True)
        outgoing = OUTGOING
        # create new SMS
        self.create_batch(SMSFactory, 3, direction=outgoing, start=10, carrier=self.vumi_backend)
        audit_sms.delay()
        discrepancies = models.Discrepancy.objects.all()
        # SMS created within the last 24 hours will not be audited and should
        # not create any new discrepancies.
        self.assertEqual(discrepancies.count(), 0)
