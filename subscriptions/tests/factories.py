import factory

from libya_site.tests.factories import UserFactory
from subscriptions import models


class SubscriptionFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.Subscription

    user = factory.SubFactory(UserFactory)
