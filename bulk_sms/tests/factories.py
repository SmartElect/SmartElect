import factory

from bulk_sms import models
from libya_elections.phone_numbers import get_random_phone_number
from libya_site.tests.factories import UserFactory
from register.tests.factories import SMSFactory


class BatchFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.Batch

    created_by = factory.SubFactory(UserFactory)
    reviewed_by = factory.SubFactory(UserFactory)


class BulkMessageFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.BulkMessage

    phone_number = factory.Sequence(lambda n: get_random_phone_number())
    message = factory.fuzzy.FuzzyText()
    batch = factory.SubFactory(BatchFactory)
    sms = factory.SubFactory(SMSFactory)


class BroadcastFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.Broadcast

    created_by = factory.SubFactory(UserFactory)
    batch = factory.SubFactory(BatchFactory)
