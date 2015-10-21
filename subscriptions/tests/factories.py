import factory

from libya_site.tests.factories import UserFactory
from subscriptions import models


class SubscriptionFactory(factory.DjangoModelFactory):
    FACTORY_FOR = models.Subscription

    user = factory.SubFactory(UserFactory)
