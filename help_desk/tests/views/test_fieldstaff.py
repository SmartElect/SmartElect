from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from help_desk.models import FieldStaff, HELP_DESK_MANAGERS_GROUP
from help_desk.tests.factories import HelpDeskManagerFactory, FieldStaffFactory
from help_desk.utils import create_help_desk_groups
from libya_elections.utils import permission_names_to_objects
from libya_site.tests.factories import DEFAULT_USER_PASSWORD
from libya_elections.phone_numbers import get_random_phone_number


class FieldStaffViewsTest(TestCase):
    def setUp(self):
        create_help_desk_groups()
        self.manager = HelpDeskManagerFactory()
        assert self.client.login(
            username=self.manager.username,
            password=DEFAULT_USER_PASSWORD)

    def test_list(self):
        for i in range(3):
            FieldStaffFactory()
        url = reverse('browse_fieldstaff')
        rsp = self.client.get(url)
        object_list = rsp.context['object_list']
        self.assertEqual(3, len(object_list))

    def test_search_name(self):
        target = FieldStaffFactory(name='Freddy')
        for i in range(2):
            FieldStaffFactory()
        url = reverse('browse_fieldstaff') + "?q=Fred"
        rsp = self.client.get(url)
        object_list = rsp.context['object_list']
        self.assertEqual(1, len(object_list))
        self.assertIn(target, object_list)

    def test_search_id(self):
        # Create a phone number that's sure not to conflict with the staff_ids. If I don't do this,
        # the randomly-generated phone number might match the staff_id param in the view.
        phone_number = '55555555555'
        target = FieldStaffFactory(name='Freddy', staff_id=999, phone_number=phone_number)
        for i in range(2):
            FieldStaffFactory(staff_id=100 + i, phone_number=phone_number)
        url = reverse('browse_fieldstaff') + "?q=%d" % target.staff_id
        rsp = self.client.get(url)
        object_list = rsp.context['object_list']
        self.assertEqual(1, len(object_list))
        self.assertIn(target, object_list)

    def test_search_phone(self):
        number = get_random_phone_number()
        target = FieldStaffFactory(phone_number=number, suspended=False)
        for i in range(2):
            FieldStaffFactory()
        url = reverse('browse_fieldstaff') + "?q=%s" % number
        rsp = self.client.get(url)
        object_list = rsp.context['object_list']
        self.assertEqual(1, len(object_list))
        self.assertIn(target, object_list)

    def test_create(self):
        data = {
            'name': 'Fred',
            'phone_number': get_random_phone_number(),
            'staff_id': 892,
            'suspended': False,
        }
        url = reverse('add_fieldstaff')
        rsp = self.client.post(url, data=data)
        self.assertRedirects(rsp, reverse('browse_fieldstaff'))

    def test_create_bad(self):
        data = {
            'name': 'Fred',
            'phone_number': get_random_phone_number(),
            'staff_id': 'wzyw',
            'suspended': False,
        }
        url = reverse('add_fieldstaff')
        rsp = self.client.post(url, data=data)
        self.assertEqual(400, rsp.status_code)
        self.assertFalse(FieldStaff.objects.filter(name='Fred').exists())

    def test_update(self):
        staff = FieldStaffFactory(suspended=False)
        data = {
            'name': 'Fred',
            'phone_number': get_random_phone_number(),
            'staff_id': 892,
            'suspended': True,
        }
        url = reverse('edit_fieldstaff', kwargs={'pk': staff.pk})
        self.client.post(url, data=data)
        new_staff = FieldStaff.objects.get(pk=staff.pk)
        self.assertEqual(data['name'], new_staff.name)
        self.assertEqual(data['phone_number'], new_staff.phone_number)
        self.assertEqual(data['staff_id'], new_staff.staff_id)
        self.assertTrue(new_staff.suspended)

    def test_create_no_suspend_perm(self):
        # strip Manager of suspend_fieldstaff perm
        user = self.manager
        perms = user.get_group_permissions()
        perms.remove('help_desk.suspend_fieldstaff')
        group = Group.objects.get(name=HELP_DESK_MANAGERS_GROUP)
        user.groups.remove(group)
        perm_objects = permission_names_to_objects(perms)
        user.user_permissions.add(*perm_objects)

        url = reverse('add_fieldstaff')
        rsp = self.client.get(url)
        self.assertNotContains(rsp, 'suspended')

    def test_update_no_suspend_perm(self):
        # strip Manager of suspend_fieldstaff perm
        user = self.manager
        perms = user.get_group_permissions()
        perms.remove('help_desk.suspend_fieldstaff')
        group = Group.objects.get(name=HELP_DESK_MANAGERS_GROUP)
        user.groups.remove(group)
        perm_objects = permission_names_to_objects(perms)
        user.user_permissions.add(*perm_objects)

        staff = FieldStaffFactory(suspended=False)
        url = reverse('edit_fieldstaff', kwargs={'pk': staff.pk})
        rsp = self.client.get(url)
        self.assertNotContains(rsp, 'suspended')
