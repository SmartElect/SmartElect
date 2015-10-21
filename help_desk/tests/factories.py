import factory

from django.contrib.auth.models import Group

from libya_elections.phone_numbers import get_random_phone_number
from libya_site.tests.factories import UserFactory

from ..models import Case, FieldStaff, HELP_DESK_MANAGERS_GROUP, HELP_DESK_OPERATORS_GROUP


class HelpDeskUserFactory(UserFactory):
    @factory.post_generation
    def post(self, create, extracted, **kwargs):
        operators_group = Group.objects.get(name=HELP_DESK_OPERATORS_GROUP)
        self.groups.add(operators_group)


class HelpDeskManagerFactory(HelpDeskUserFactory):
    @factory.post_generation
    def post(self, create, extracted, **kwargs):
        manager_group = Group.objects.get(name=HELP_DESK_MANAGERS_GROUP)
        self.groups.add(manager_group)


class CaseFactory(factory.DjangoModelFactory):
    FACTORY_FOR = Case

    operator = factory.SubFactory(HelpDeskUserFactory)


class FieldStaffFactory(factory.DjangoModelFactory):
    FACTORY_FOR = FieldStaff

    # Staff ID's start at 100
    staff_id = factory.Sequence(lambda n: n + 100)
    name = factory.Sequence(lambda n: 'field staff {}'.format(n))
    phone_number = factory.Sequence(lambda n: get_random_phone_number())
