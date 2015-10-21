from django import test
from django.core import mail

from subscriptions import models
from subscriptions.tests.factories import SubscriptionFactory
from subscriptions.utils import send_notifications


class SendNotificationsTest(test.TestCase):
    def setUp(self):
        SubscriptionFactory.create_batch(size=10)

    def test_notifications_sent(self):
        send_notifications(subscription_type=models.Subscription.DISCREPANCIES)
        self.assertEqual(len(mail.outbox), 10)
