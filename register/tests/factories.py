# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import division
import random

from django.conf import settings
from django.db.models import Max
from django.utils.timezone import now
import factory
import factory.fuzzy
from rapidsms import models as rapidsms_models

from civil_registry.models import Citizen
from civil_registry.tests.factories import CitizenFactory
from libya_elections.constants import MALE, INCOMING
from libya_elections.utils import random_string
from register import models


def get_unused_gender_appropriate_national_id(stub):
    if stub.gender == MALE:
        min_nid = 100000000000
        max_nid = 199999999999
    else:
        min_nid = 200000000000
        max_nid = 299999999999
    # Find the max nid in use in the desired range, among Citizens.
    max_citizen_nid = Citizen.objects.unfiltered()\
        .filter(national_id__gte=min_nid, national_id__lte=max_nid)\
        .aggregate(max=Max('national_id'))['max'] \
        or min_nid - 1
    # Use the next one, or the first one in the desired range
    return max(1 + max_citizen_nid, min_nid)


class PersonFactory(factory.DjangoModelFactory):
    FACTORY_FOR = models.Person

    # If no civil_registry_id was provided, create a Citizen.
    citizen = factory.SubFactory(CitizenFactory)

    @classmethod
    def _setup_next_sequence(cls):
        """Set up an initial sequence value for Sequence attributes.

        Returns:
            int: the first available ID to use for instances of this factory.

        Note: If we don't override this, then DjangoModelFactory bases
        the initial value on the max PK of the corresponding model,
        which in my case is absolutely huge and breaks the way we come
        up with a valid national ID, above.
        """
        # Needs to start at one so the first national ID will be valid (100000000000)
        return 1


class BackendFactory(factory.DjangoModelFactory):
    FACTORY_FOR = rapidsms_models.Backend

    # Pick a valid backend name each time
    name = factory.LazyAttribute(lambda o: random.choice(settings.INSTALLED_BACKENDS.keys()))

    # Don't really create a new one if one exists with the backend name
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        return model_class.objects.get_or_create(*args, **kwargs)[0]


class ConnectionFactory(factory.DjangoModelFactory):
    FACTORY_FOR = rapidsms_models.Connection

    identity = factory.LazyAttribute(lambda o: random_string(12))
    backend = factory.SubFactory(BackendFactory)


class SMSFactory(factory.DjangoModelFactory):
    FACTORY_FOR = models.SMS

    from_number = factory.Sequence(lambda n: ('1111111111-%s' % n)[:15])
    to_number = factory.Sequence(lambda n: ('2222222222-%s' % n)[:15])
    citizen = factory.SubFactory(CitizenFactory)
    carrier = factory.SubFactory(BackendFactory)
    msg_type = models.SMS.REGISTRATION
    direction = INCOMING
    message = "sms message"
    uuid = factory.Sequence(lambda n: 'uuid-sms-%s' % n)


class OfficeFactory(factory.DjangoModelFactory):
    FACTORY_FOR = models.Office

    id = factory.sequence(lambda n: n)
    region = models.Office.REGION_WEST


def come_up_with_unique_id_for_constituency(obj):
    max_in_use = models.Constituency.objects.aggregate(max=Max('id'))['max'] or 0
    return 1 + max_in_use


class ConstituencyFactory(factory.DjangoModelFactory):
    FACTORY_FOR = models.Constituency

    # 'id' is the primary key but it's not an auto field so we
    # need to come up with a unique value for it if it
    # wasn't specified in the factory call
    id = factory.LazyAttribute(come_up_with_unique_id_for_constituency)


def come_up_with_unique_id_for_subconstituency(obj):
    max_in_use = models.SubConstituency.objects.aggregate(max=Max('id'))['max'] or 0
    return 1 + max_in_use


class SubConstituencyFactory(factory.DjangoModelFactory):
    FACTORY_FOR = models.SubConstituency

    id = factory.LazyAttribute(come_up_with_unique_id_for_subconstituency)
    name_arabic = factory.Sequence(lambda n: 'الدائرة الفرعية ' + str(n))
    name_english = factory.Sequence(lambda n: 'Subconstituency ' + str(n))


class RegistrationCenterFactory(factory.DjangoModelFactory):
    FACTORY_FOR = models.RegistrationCenter

    # Center IDs are 5 digits
    center_id = factory.Sequence(lambda n: n + 10000)
    name = factory.Sequence(lambda n: "Center %d" % n)
    constituency = factory.SubFactory(ConstituencyFactory)
    subconstituency = factory.SubFactory(SubConstituencyFactory)
    office = factory.SubFactory(OfficeFactory)
    copy_of = None

    @factory.post_generation
    def post(instance, create, extracted, **kwargs):
        """Ensure copy_of and center_type are in sync"""
        if instance.copy_of:
            instance.center_type = models.RegistrationCenter.Types.COPY
        else:
            if instance.center_type == models.RegistrationCenter.Types.COPY:
                instance.copy_of = RegistrationCenterFactory()


class RegistrationFactory(factory.DjangoModelFactory):
    FACTORY_FOR = models.Registration

    citizen = factory.SubFactory(CitizenFactory)
    registration_center = factory.SubFactory(RegistrationCenterFactory)
    archive_time = factory.LazyAttribute(lambda foo: now())
    sms = factory.SubFactory(SMSFactory)


class BlacklistFactory(factory.DjangoModelFactory):
    FACTORY_FOR = models.Blacklist


class WhitelistFactory(factory.DjangoModelFactory):
    FACTORY_FOR = models.Whitelist
