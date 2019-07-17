import os

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from register.models import RegistrationCenter, Registration
from register.tests.factories import SubConstituencyFactory, RegistrationCenterFactory, \
    RegistrationFactory


class DevNullMixin():
    "Open and close a handle to /dev/null to quiet mgmt commmand output during tests"
    def setUp(self):
        self.devnull = open(os.devnull, 'w')

    def tearDown(self):
        self.devnull.close()


class SetRegOpenTest(DevNullMixin, TestCase):
    def test_all_or_subcons_not_both(self):
        "Should not be able to choose subcons and choose --all."
        subconstituency = SubConstituencyFactory()
        with self.assertRaises(CommandError) as cm:
            call_command('set_reg_open', str(subconstituency.id), all=True,
                         stdout=self.devnull)
        self.assertEqual(str(cm.exception),
                         'Choose either --all or provide a list of subcons, not both.')

    def test_must_choose_some_centers(self):
        "Must choose either subcons or --all"
        with self.assertRaises(CommandError) as cm:
            call_command('set_reg_open', stdout=self.devnull)
        self.assertEqual(str(cm.exception),
                         'Neither --all nor subcon_ids were provided.')

    def test_set_all_open(self):
        "Can set reg_open=True."
        # start with centers whose reg_open=False
        RegistrationCenterFactory.create_batch(5, reg_open=False)
        call_command('set_reg_open', all=True, stdout=self.devnull)
        open_count = RegistrationCenter.objects.filter(reg_open=True).count()
        self.assertEqual(5, open_count)

    def test_set_all_closed(self):
        "Can set reg_open=False"
        # start with centers whose reg_open=True
        RegistrationCenterFactory.create_batch(5, reg_open=True)
        call_command('set_reg_open', reg_open=False, all=True, stdout=self.devnull)
        closed_count = RegistrationCenter.objects.filter(reg_open=False).count()
        self.assertEqual(5, closed_count)

    def test_subconstituency(self):
        "If we choose a subconstituency, only change those subconstituencies."
        other_subcon = SubConstituencyFactory()
        target_subcon = SubConstituencyFactory()
        RegistrationCenterFactory.create(reg_open=False, subconstituency=other_subcon)
        RegistrationCenterFactory.create(reg_open=False, subconstituency=target_subcon)
        call_command('set_reg_open', str(target_subcon.id), stdout=self.devnull)
        for rc in RegistrationCenter.objects.all():
            if rc.subconstituency == target_subcon:
                self.assertTrue(rc.reg_open)
            else:
                self.assertFalse(rc.reg_open)


class SetRemainingChangesTest(DevNullMixin, TestCase):

    def test_all_or_subcons_not_both(self):
        "Should not be able to choose subcons and choose --all."
        subconstituency = SubConstituencyFactory()
        with self.assertRaises(CommandError) as cm:
            call_command('set_remaining_changes', str(subconstituency.id), all=True,
                         stdout=self.devnull)
        self.assertEqual(str(cm.exception),
                         'Choose either --all or provide a list of subcons, not both.')

    def test_must_choose_some_registrations(self):
        "Should not be able to choose subcons and choose --all."
        with self.assertRaises(CommandError) as cm:
            call_command('set_remaining_changes', stdout=self.devnull)
        self.assertEqual(str(cm.exception), 'Neither --all nor subcon_ids were provided.')

    def test_must_choose_a_value_for_remaining_changes(self):
        "Must choose --zero, --one, or --max."
        with self.assertRaises(CommandError) as cm:
            call_command('set_remaining_changes', all=True, stdout=self.devnull)
        self.assertEqual(str(cm.exception),
                         'Provide --zero, --one, or --max to specify # of changes allowed.')

    def test_set_remaining_to_none(self):
        reg = RegistrationFactory(max_changes=3, change_count=0, archive_time=None)
        call_command('set_remaining_changes', all=True, remaining=0,
                     stdout=self.devnull)
        reg = Registration.objects.get()
        self.assertEqual(reg.change_count, reg.max_changes)

    def test_set_remaining_to_one(self):
        RegistrationFactory(max_changes=3, change_count=0, archive_time=None)
        call_command('set_remaining_changes', all=True, remaining=1,
                     stdout=self.devnull)
        reg = Registration.objects.first()
        self.assertEqual(reg.change_count, reg.max_changes - 1)

    def test_set_remaining_to_max(self):
        RegistrationFactory(max_changes=3, change_count=3, archive_time=None)
        call_command('set_remaining_changes', all=True, remaining=-1,
                     stdout=self.devnull)
        reg = Registration.objects.first()
        self.assertEqual(reg.change_count, 0)

    def test_subconstituency(self):
        "If we choose a subconstituency, only change registrations in those subconstituencies."
        other_subcon = SubConstituencyFactory()
        target_subcon = SubConstituencyFactory()
        RegistrationFactory(registration_center__subconstituency=other_subcon)
        RegistrationFactory(registration_center__subconstituency=target_subcon)
        call_command('set_remaining_changes', str(target_subcon.id), remaining=0,
                     stdout=self.devnull)
        for reg in Registration.objects.all():
            if reg.registration_center.subconstituency == target_subcon:
                self.assertEqual(reg.change_count, reg.max_changes)
            else:
                self.assertNotEqual(reg.change_count, reg.max_changes)
