from django.utils.timezone import now

import factory

from audit import models
from libya_elections.constants import INCOMING
from register.tests.factories import SMSFactory


class VumiLogFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.VumiLog

    uuid = factory.Sequence(lambda n: 'uuid-vumilog-%s' % n)
    logged_date = now()
    direction = INCOMING
    to_addr = factory.Sequence(lambda n: '2222222222-%s' % n)
    from_addr = factory.Sequence(lambda n: '1111111111-%s' % n)
    content = 'vumilog message'
    raw_text = 'bunch of logged information'


class SMSTrailFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.SMSTrail

    sms = factory.SubFactory(SMSFactory)
    vumi = factory.SubFactory(VumiLogFactory)


class DiscrepancyFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.Discrepancy

    trail = factory.SubFactory(SMSTrailFactory)
