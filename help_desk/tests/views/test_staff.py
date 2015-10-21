from django.contrib.auth.models import User, Group
from django.core.urlresolvers import reverse
from django.test import TestCase
from help_desk.models import HELP_DESK_OPERATORS_GROUP, HELP_DESK_SUPERVISORS_GROUP
from help_desk.tests.factories import HelpDeskManagerFactory
from help_desk.utils import create_help_desk_groups
from libya_site.tests.factories import DEFAULT_USER_PASSWORD, UserFactory


class TestStaffViews(TestCase):
    def setUp(self):
        create_help_desk_groups()
        self.manager = HelpDeskManagerFactory()
        assert self.client.login(
            username=self.manager.username,
            password=DEFAULT_USER_PASSWORD)

    def test_staff_create(self):
        group = Group.objects.get(name=HELP_DESK_OPERATORS_GROUP)
        data = {
            'username': 'fred',
            'first_name': 'Fred',
            'last_name': 'Boggs',
            'email': 'fred.boggs@example.com',
            'password1': 'qwerty',
            'password2': 'qwerty',
            'help_desk_group': group.name,
        }
        url = reverse('staff_create')
        rsp = self.client.post(url, data=data)
        self.assertRedirects(rsp, reverse('staff_list'), msg_prefix=rsp.content.decode('utf-8'))
        user = User.objects.get(username='fred')
        self.assertEqual(user.last_name, 'Boggs')
        self.assertTrue(user.check_password('qwerty'))

    def test_staff_create_mismatched_pass(self):
        data = {
            'username': 'fred',
            'first_name': 'Fred',
            'last_name': 'Boggs',
            'email': 'fred.boggs@example.com',
            'password1': 'qwerty',
            'password2': 'zzwwy',
        }
        url = reverse('staff_create')
        rsp = self.client.post(url, data=data)
        self.assertEqual(200, rsp.status_code)
        with self.assertRaises(User.DoesNotExist):
            User.objects.get(username='fred')

    def test_staff_update(self):
        group = Group.objects.get(name=HELP_DESK_SUPERVISORS_GROUP)
        user = UserFactory(username='joe', first_name='Jeff', last_name='Doe',
                           password='puppy')
        url = reverse('staff_update', kwargs={'pk': user.pk})
        data = {
            'username': 'fred',
            'first_name': 'Fred',
            'last_name': 'Boggs',
            'email': 'fred.boggs@example.com',
            'help_desk_group': group.name,
        }
        self.client.post(url, data=data)
        user = User.objects.get(username='fred')
        self.assertEqual(user.last_name, 'Boggs')
        self.assertTrue(user.check_password('puppy'))
        self.assertIn(group, user.groups.all())
        self.assertEqual(1, user.groups.count())

    def test_set_password_match(self):
        user = UserFactory(username='joe', first_name='Jeff', last_name='Doe',
                           password='puppy')
        url = reverse('staff_set_password', kwargs={'pk': user.pk})
        data = {
            'new_password1': 'foo',
            'new_password2': 'foo',
        }
        rsp = self.client.post(url, data=data, follow=False)
        self.assertEqual(302, rsp.status_code)
        user = User.objects.get(pk=user.pk)
        self.assertTrue(user.check_password('foo'))

    def test_set_password_mismatch(self):
        user = UserFactory(username='joe', first_name='Jeff', last_name='Doe',
                           password='puppy')
        url = reverse('staff_set_password', kwargs={'pk': user.pk})
        data = {
            'new_password1': 'foo',
            'new_password2': 'bar',
        }
        rsp = self.client.post(url, data=data, follow=False)
        self.assertEqual(200, rsp.status_code)
        user = User.objects.get(pk=user.pk)
        self.assertTrue(user.check_password('puppy'))

    def test_staff_search(self):
        url = reverse('staff_search')
        user = User.objects.create(username='fred', first_name='joe', last_name='moe')
        user2 = User.objects.create(username='barney', first_name='wilma', last_name='flintstone')
        rsp = self.client.get(url + "?q=fred")
        object_list = rsp.context['object_list']
        self.assertEqual(1, len(object_list))
        self.assertIn(user, object_list)
        rsp = self.client.get(url + "?q=flint")
        object_list = rsp.context['object_list']
        self.assertEqual(1, len(object_list))
        self.assertIn(user2, object_list)
        rsp = self.client.get(url)  # No search - on this page, should return no results
        object_list = rsp.context['object_list']
        self.assertEqual(0, len(object_list), object_list)
