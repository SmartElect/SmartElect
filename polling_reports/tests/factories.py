import factory

from libya_elections.phone_numbers import get_random_phone_number
from polling_reports import models
from register.tests.factories import RegistrationCenterFactory
from libya_elections.constants import FIRST_PERIOD_NUMBER
from voting.models import Election
from voting.tests.factories import ElectionFactory


def get_or_create_election(stub):
    """Return a current election if one exists, or create a new one using ElectionFactory"""
    election = Election.objects.get_most_current_election()
    return election if election else ElectionFactory()


class PollingReportFactory(factory.DjangoModelFactory):
    FACTORY_FOR = models.PollingReport

    election = factory.LazyAttribute(get_or_create_election)
    registration_center = factory.SubFactory(RegistrationCenterFactory)
    period_number = FIRST_PERIOD_NUMBER
    num_voters = factory.Sequence(int)
    phone_number = factory.Sequence(lambda n: get_random_phone_number())


class CenterOpenFactory(factory.DjangoModelFactory):
    FACTORY_FOR = models.CenterOpen

    election = factory.LazyAttribute(get_or_create_election)
    registration_center = factory.SubFactory(RegistrationCenterFactory)


class StaffPhoneFactory(factory.DjangoModelFactory):
    FACTORY_FOR = models.StaffPhone

    registration_center = factory.SubFactory(RegistrationCenterFactory)
    phone_number = factory.Sequence(lambda n: get_random_phone_number())
