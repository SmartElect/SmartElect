import factory
from civil_registry.tests.factories import CitizenFactory
from libya_site.tests.factories import UserFactory

from ..models import Changeset, ChangeRecord


class ChangesetFactory(factory.DjangoModelFactory):
    class Meta:
        model = Changeset

    name = factory.Sequence(lambda n: "changeset %d" % n)
    justification = "Just do it"
    created_by = factory.SubFactory(UserFactory)


class ChangeRecordFactory(factory.DjangoModelFactory):
    class Meta:
        model = ChangeRecord

    changeset = factory.SubFactory(ChangesetFactory)
    changed = True
    change = Changeset.CHANGE_CENTER
    citizen = factory.SubFactory(CitizenFactory)
