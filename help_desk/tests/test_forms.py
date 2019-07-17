from datetime import timedelta

from django.test import TestCase
from django.utils.timezone import now

from help_desk.forms import NewUserForm, UpdateUserForm
from help_desk.models import ActiveRange
from libya_elections.constants import LIBYA_DATE_FORMAT
from libya_site.tests.factories import UserFactory


class HelpDeskStaffUserFormTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.staff_user = UserFactory()
        cls.staff_user.is_staff = True
        cls.staff_user.save()
        cls.help_desk_user = UserFactory()

    def setUp(self):
        tomorrow = now().date() + timedelta(days=1)
        self.data = {
            'username': 'foo',
            'password1': 'secret',
            'password2': 'secret',
            'end_date': tomorrow.strftime(LIBYA_DATE_FORMAT),
        }

    # Create form

    def test_create_form_creates_active_range(self):
        form = NewUserForm(user=self.staff_user, data=self.data)
        self.assertTrue(form.is_valid(), form.errors)

        new_user = form.save()
        self.assertEqual(new_user.active_range.end_date.strftime(LIBYA_DATE_FORMAT),
                         self.data['end_date'])

    def test_create_form_dates_are_not_required(self):
        self.data.update({
            'end_date': '',
        })
        form = NewUserForm(user=self.staff_user, data=self.data)
        self.assertTrue(form.is_valid(), form.errors)

        new_user = form.save()
        self.assertEqual(new_user.active_range.end_date, None)

    def test_create_form_end_date_must_be_in_future(self):
        self.data.update({
            'end_date': '01/01/2018',  # < -past date
        })
        form = NewUserForm(user=self.staff_user, data=self.data)
        self.assertFalse(form.is_valid())
        self.assertIn('End date cannot be in the past', str(form.errors))

    # Update form

    def test_update_form_creates_active_range_if_not_present(self):
        # assert that user doesn't have an active_range related object
        self.assertFalse(hasattr(self.help_desk_user, 'active_range'))
        form = UpdateUserForm(user=self.staff_user, data=self.data,
                              instance=self.help_desk_user)
        self.assertTrue(form.is_valid(), form.errors)

        updated_user = form.save()
        # now it does!
        self.assertTrue(updated_user.active_range)

    def test_update_form_updates_active_range_if_present(self):
        # active_range.end_date is set to 2018-01-01
        active_range = ActiveRange.objects.create(user=self.help_desk_user, end_date='2018-01-01')
        self.assertTrue(hasattr(self.help_desk_user, 'active_range'))
        form = UpdateUserForm(user=self.staff_user, data=self.data,
                              instance=self.help_desk_user)
        form.save()
        active_range.refresh_from_db()
        # now it's updated
        self.assertEqual(active_range.end_date.strftime(LIBYA_DATE_FORMAT),
                         self.data['end_date'])

    def test_update_form_dates_are_not_required(self):
        self.data.update({
            'end_date': '',
        })
        form = UpdateUserForm(user=self.staff_user, data=self.data,
                              instance=self.help_desk_user)
        updated_user = form.save()
        self.assertEqual(updated_user.active_range.end_date, None)

    def test_update_form_end_date_must_be_in_future(self):
        self.data.update({
            'end_date': '01/01/2018',  # < -past date
        })
        form = UpdateUserForm(user=self.staff_user, data=self.data,
                              instance=self.help_desk_user)
        self.assertFalse(form.is_valid())
        self.assertIn('End date cannot be in the past', str(form.errors))
