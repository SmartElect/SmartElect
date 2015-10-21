from datetime import date
import random

import factory
import factory.fuzzy

from civil_registry.models import Citizen, TempCitizen
from libya_elections.constants import MALE


def get_nid(stub):
    # Stupidity to avoid circular import
    from register.tests.factories import get_unused_gender_appropriate_national_id
    return get_unused_gender_appropriate_national_id(stub)


def get_unused_civil_registry_id(stub):
    """Return an unused civil registry id.

    This is subject to a race condition that's a bit difficult to fix here in factoryland.
    """
    civil_registry_id = random.randint(1, 999999999)
    while Citizen.objects.filter(pk=civil_registry_id).exists():
        civil_registry_id = random.randint(1, 999999999)
    return civil_registry_id


class CitizenFactory(factory.DjangoModelFactory):
    """
    Create a Citizen for testing.
    """
    FACTORY_FOR = Citizen

    civil_registry_id = factory.LazyAttribute(get_unused_civil_registry_id)
    national_id = factory.LazyAttribute(get_nid)
    # Default to old enough to vote
    birth_date = date(1913, 2, 3)
    gender = MALE
    fbr_number = factory.fuzzy.FuzzyInteger(1, 99999999)

    first_name = factory.fuzzy.FuzzyText()
    father_name = factory.fuzzy.FuzzyText()
    grandfather_name = factory.fuzzy.FuzzyText()
    mother_name = factory.fuzzy.FuzzyText()
    family_name = factory.fuzzy.FuzzyText()
    missing = None

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
        return 1


class TempCitizenFactory(CitizenFactory):
    FACTORY_FOR = TempCitizen
