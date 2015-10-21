# -*- coding: utf-8 -*-

# Python imports
import datetime
from decimal import Decimal
import string

# Django imports
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.db import connection
from django.db.models.fields import FieldDoesNotExist
from django.test import TestCase
from django.utils import translation
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

# 3rd party imports
from pytz import timezone, utc

# Project imports
from ..constants import EASTERN_ARABIC_DIGITS, ARABIC_COMMA
from ..utils import ConnectionInTZ, cleanup_lat_or_long, _extract_numerals, \
    get_db_connection_tz, max_non_none_datetime, min_non_none_datetime, \
    parse_latlong, get_random_number_string, shuffle_string, find_overlapping_records, \
    get_verbose_name, get_comma_delimiter
from .utils import ResponseCheckerMixin
from register.models import Office
from staff.tests.base import StaffUserMixin
from voting.models import RegistrationPeriod
from voting.tests.factories import RegistrationPeriodFactory


class UtilsTest(TestCase):
    def test_max_non_none_datetime(self):
        date2 = now().astimezone(utc)
        libya_tz = timezone('Libya')
        date1 = libya_tz.normalize((date2 - datetime.timedelta(hours=1)).astimezone(libya_tz))
        et_tz = timezone('EST5EDT')
        date3 = libya_tz.normalize((date2 + datetime.timedelta(hours=1)).astimezone(et_tz))
        self.assertEqual(date3, max_non_none_datetime(date1, date2, date3))
        self.assertEqual(date3, max_non_none_datetime(date3))
        self.assertIsNone(max_non_none_datetime(None))
        self.assertIsNone(max_non_none_datetime())

    def test_min_non_none_datetime(self):
        date2 = now().astimezone(utc)
        libya_tz = timezone('Libya')
        date1 = libya_tz.normalize((date2 - datetime.timedelta(hours=1)).astimezone(libya_tz))
        et_tz = timezone('EST5EDT')
        date3 = libya_tz.normalize((date2 + datetime.timedelta(hours=1)).astimezone(et_tz))
        self.assertEqual(date1, min_non_none_datetime(date1, date2, date3))
        self.assertEqual(date3, min_non_none_datetime(date3))
        self.assertIsNone(min_non_none_datetime(None))
        self.assertIsNone(min_non_none_datetime())

    def test_cleanup_lat_long(self):
        # Test conversions

        def coord(degrees, minutes, seconds):
            # Return the Decimal equivalent of the given degrees, minutes, seconds coordinate
            val = degrees + (minutes/60.0) + (seconds/3600.0)
            return parse_latlong(val)

        for input, expected_output in [
            (u"10ْ .05 30 63", coord(10, 5, 30.63)),
            (u"10.1826", Decimal('10.18260000')),
            (u"12.2", Decimal('12.2')),
            (u"12° 2", coord(12, 2, 0)),
            (u"12° 2'54.62\"", coord(12, 2, 54.62)),
            (u"12ْ 14 23", coord(12, 14, 23)),
            (u"12°37'7.00\"", coord(12, 37, 7.0)),
            (u"12° 2'54.62\"", coord(12, 2, 54.62)),
            (u"12°37'7.00\"", coord(12, 37, 7.00)),
            (u"12°37'49.30\"", coord(12, 37, 49.30)),
            (u"14ْ 25 816", None),
            (u"204650", coord(20, 46, 50)),
            (u"290250", coord(29, 2, 50)),
            (u"32ْ 453 700", None),
            (u"57 \" .579\" .12", None),
            (u"1234", None),
        ]:
            result = cleanup_lat_or_long(input)
            if expected_output is None:
                self.assertIsNone(result,
                                  msg="On input %r, expected None but got %r" % (input, result))
            else:
                self.assertEqual(result, expected_output,
                                 msg="On input %r, expected %r but got %r"
                                     % (input, expected_output, result))

    def test_db_tz_context(self):
        db_cursor = connection.cursor()
        current_tz = get_db_connection_tz(db_cursor)
        with ConnectionInTZ(db_cursor, settings.TIME_ZONE):
            # This expectation is based on Django keeping the TZ in UTC and
            # settings.TIME_ZONE being a different (local) TZ.
            self.assertFalse(get_db_connection_tz(db_cursor) == current_tz)
        self.assertTrue(get_db_connection_tz(db_cursor) == current_tz)

    def test_get_comma_delimiter(self):
        """Exercise get_comma_delimiter()"""
        translation.activate('ar')
        self.assertEqual(get_comma_delimiter(False), ARABIC_COMMA)
        self.assertEqual(get_comma_delimiter(), ARABIC_COMMA + ' ')
        translation.deactivate()

        translation.activate('en')
        self.assertEqual(get_comma_delimiter(False), ',')
        self.assertEqual(get_comma_delimiter(), ', ')
        translation.deactivate()


class GetVerboseNameTest(TestCase):
    """Exercise get_verbose_name()"""
    def test_with_model(self):
        """Ensure a model is accepted as a param"""
        self.assertEqual(get_verbose_name(Office, 'region'), "Region")

    def test_with_instance(self):
        """Ensure a model instance is accepted as a param"""
        self.assertEqual(get_verbose_name(Office(), 'region'), "Region")

    def test_no_init_cap(self):
        """Ensure init cap is optional"""
        self.assertEqual(get_verbose_name(Office(), 'region', False), "region")

    def test_field_with_no_explicit_verbose_name(self):
        """Test behavior with a field to which we haven't given an explicit name"""
        self.assertEqual(get_verbose_name(Office(), 'id'), "Id")

    def test_failure(self):
        """Ensure FieldDoesNotExist is raised no matter what trash is passed as the field name"""
        for field_name in ('kjasfhkjdh', u'sfasfda', None, 42, False, complex(42), lambda: None,
                           ValueError(), _('English'), {}, [], tuple()):
            with self.assertRaises(FieldDoesNotExist):
                get_verbose_name(Office, field_name)


class StandardizeInputTest(TestCase):

    def _build_io_table(self, nid, center_id, a_digit):
        """Takes nid, center_id, and any one digit (char) in your desired language
        and builds a list of (input, output) entries that you can assertEqual
        """
        expected = [nid, center_id]
        return [
            # test lots of spaces
            (u"  %s   * %s  " % (nid, center_id), expected),
            # test mixed spaces
            (u"%s* %s  " % (nid, center_id), expected),
            # test one number only
            (nid, [nid]),
            # test nid-first combinations
            (u"%s %s" % (nid, center_id), expected),
            (u"%s*%s" % (nid, center_id), expected),
            (u"%s#%s" % (nid, center_id), expected),
            (u"blah%sblah%sblah" % (nid, center_id), expected),
            # test short nid
            (u"%s %s" % (nid[:-1], center_id), [nid[:-1], center_id]),
            # test long nid
            (u"%s %s" % (nid + a_digit, center_id), [nid + a_digit, center_id]),
            # test short center_id
            (u"%s %s" % (nid, center_id[:-1]), [nid, center_id[:-1]]),
            # test long center_id
            (u"%s %s" % (nid, center_id + a_digit), [nid, center_id + a_digit]),
            # test both short
            (u"%s %s" % (nid[:-1], center_id[-1]), [nid[:-1], center_id[-1]]),
            # test both long
            (u"%s %s" % (nid + a_digit, center_id + a_digit), [nid + a_digit, center_id + a_digit]),
            # test 3 number input returns all numbers
            (u"%s %s %s" % (nid, center_id, a_digit), [nid, center_id, a_digit]),
        ]

    def test_extract_arabic_numerals(self):
        nid = (get_random_number_string(length=12, choices=EASTERN_ARABIC_DIGITS))
        center_id = get_random_number_string(length=5, choices=EASTERN_ARABIC_DIGITS)
        io_table = self._build_io_table(nid, center_id, EASTERN_ARABIC_DIGITS[3])
        for (input, expected_output) in io_table:
            self.assertEqual(_extract_numerals(input), expected_output)

    def test_extract_american_numerals(self):
        nid = get_random_number_string(length=12)
        center_id = get_random_number_string(length=5)
        io_table = self._build_io_table(nid, center_id, '3')
        for (input, expected_output) in io_table:
            self.assertEqual(_extract_numerals(input), expected_output)

    def test_extract_mixed_language_numerals(self):
        nid = (get_random_number_string(length=6, choices=EASTERN_ARABIC_DIGITS) +
               get_random_number_string(length=6, choices=string.digits))
        center_id = (get_random_number_string(length=3, choices=EASTERN_ARABIC_DIGITS) +
                     get_random_number_string(length=3, choices=string.digits))
        nid = shuffle_string(nid)
        center_id = shuffle_string(center_id)
        io_table = self._build_io_table(nid, center_id, '3')
        for (input, expected_output) in io_table:
            self.assertEqual(_extract_numerals(input), expected_output)


class OverlapUtiltest(TestCase):
    """
    Test for the find_overlapping_records function.
    Uses RegistrationPeriod because it's a fairly simple model with
    a period, but any similar model would do.
    """
    def setUp(self):
        # Create an existing period.  Then we'll try creating
        # others around it.
        self.reg_period = RegistrationPeriodFactory(
            start_time=now() - datetime.timedelta(days=1),
            end_time=now() + datetime.timedelta(days=1),
        )

    def should_work(self, start_time, end_time):
        """Assert that the period with the specified start and end times
        does not overlap with the test period."""
        self.assertFalse(
            find_overlapping_records(
                start_time,
                end_time,
                RegistrationPeriod.objects.all(),
                'start_time',
                'end_time'
            )
        )

    def should_not_work(self, start_time, end_time):
        """Assert that the period with the specified start and end times
        does overlap with the test period."""
        self.assertTrue(
            find_overlapping_records(
                start_time,
                end_time,
                RegistrationPeriod.objects.all(),
                'start_time',
                'end_time'
            )
        )

    def test_completely_before(self):
        self.should_work(
            start_time=self.reg_period.start_time - datetime.timedelta(days=2),
            end_time=self.reg_period.start_time - datetime.timedelta(days=2),
        )

    def test_end_abuts_existing_start(self):
        # This should work too
        self.should_work(
            start_time=self.reg_period.start_time - datetime.timedelta(days=2),
            end_time=self.reg_period.start_time,
        )

    def test_ends_during(self):
        # New period ends during the existing period
        # This should NOT work
        self.should_not_work(
            start_time=self.reg_period.start_time - datetime.timedelta(days=2),
            end_time=self.reg_period.end_time - datetime.timedelta(seconds=1),
        )

    def test_starts_during(self):
        # New period starts during the existing period
        # This should not work
        self.should_not_work(
            start_time=self.reg_period.start_time + datetime.timedelta(seconds=1),
            end_time=self.reg_period.end_time + datetime.timedelta(days=1),
        )

    def test_start_abuts_existing_end(self):
        # This should work
        self.should_work(
            start_time=self.reg_period.end_time,
            end_time=self.reg_period.end_time + datetime.timedelta(days=1),
        )

    def test_starts_after_existing_end(self):
        # This should work
        self.should_work(
            start_time=self.reg_period.end_time + datetime.timedelta(seconds=1),
            end_time=self.reg_period.end_time + datetime.timedelta(days=1),
        )

    def test_starts_before_and_ends_after_existing(self):
        # New period encompasses existing period
        # This should not work
        self.should_not_work(
            start_time=self.reg_period.start_time - datetime.timedelta(seconds=1),
            end_time=self.reg_period.end_time + datetime.timedelta(days=1),
        )

    def test_starts_and_ends_within_existing(self):
        # new period is inside existing period
        # This should not work
        self.should_not_work(
            start_time=self.reg_period.start_time + datetime.timedelta(seconds=1),
            end_time=self.reg_period.end_time - datetime.timedelta(seconds=1),
        )

    def test_two_empty_periods_at_same_time(self):
        # Pathological case - two empty periods do not overlap,
        # even if they start and end at the same time
        RegistrationPeriod.objects.all().delete()
        time = now()
        RegistrationPeriodFactory(start_time=time, end_time=time)
        self.should_work(start_time=time, end_time=time)

    def test_two_nonempty_periods_at_same_time(self):
        # A period should conflict with another period at exactly
        # the same start and end times
        self.should_not_work(
            start_time=self.reg_period.start_time,
            end_time=self.reg_period.end_time,
        )


class LoginPermissionMixinTest(ResponseCheckerMixin, StaffUserMixin, TestCase):
    """Exercise the LoginPermissionRequiredMixin"""
    urls = 'libya_elections.tests.urls'

    def setUp(self):
        # self.model is set for StaffUserMixin. There's nothing special about the Office model,
        # I just need to pick a model for this test and Office is as good as any.
        self.model = Office
        # Add a made-up permission.
        self.permissions = ['mogrify_office']
        content_type = ContentType.objects.get_for_model(self.model)
        Permission.objects.create(codename=self.permissions[0], content_type=content_type)
        self.test_urls = (reverse('login_permission_required_view_raise_exception_false'),
                          reverse('login_permission_required_view_raise_exception_true'))
        super(LoginPermissionMixinTest, self).setUp()

    def test_login_permission_required_positive(self):
        """ensure an authenticated user with the appropriate permission can visit the page"""
        for url in self.test_urls:
            response = self.client.get(url)
            self.assertOK(response)

    def test_login_permission_required_negative_permission(self):
        """ensure an authenticated user who lacks the appropriate permission gets a 403"""
        permission = Permission.objects.get(codename=self.permissions[0])
        self.user.user_permissions.remove(permission)
        for url in self.test_urls:
            response = self.client.get(url)
            self.assertForbidden(response)

    def test_login_permission_required_negative_login(self):
        """ensure an unauthenticated user is redirected gently to the login page"""
        self.client.logout()
        for url in self.test_urls:
            response = self.client.get(url)
            self.assertRedirectsToLogin(response)


class LoginMultiplePermissionMixinsTest(ResponseCheckerMixin, StaffUserMixin, TestCase):
    """Exercise the LoginMultiplePermissionsRequiredMixin"""
    urls = 'libya_elections.tests.urls'

    def setUp(self):
        # See comments for LoginPermissionMixinsTest.
        self.model = Office
        content_type = ContentType.objects.get_for_model(self.model)
        self.permissions = ['mogrify_office', 'frob_office']

        for permission in self.permissions:
            Permission.objects.create(codename=permission, content_type=content_type)

        self.test_urls = (reverse('login_multiple_permissions_required_view_raise_exception_false'),
                          reverse('login_multiple_permissions_required_view_raise_exception_true'))

        super(LoginMultiplePermissionMixinsTest, self).setUp()

    def test_login_permission_required_positive(self):
        """ensure an authenticated user with the appropriate permission can visit the page"""
        for url in self.test_urls:
            response = self.client.get(url)
            self.assertOK(response)

    def test_login_permission_required_negative_permission(self):
        """ensure an authenticated user who lacks the appropriate permission gets a 403"""
        permission = Permission.objects.get(codename=self.permissions[0])
        self.user.user_permissions.remove(permission)
        for url in self.test_urls:
            response = self.client.get(url)
            self.assertForbidden(response)

    def test_login_permission_required_negative_login(self):
        """ensure an unauthenticated user is redirected gently to the login page"""
        self.client.logout()
        for url in self.test_urls:
            response = self.client.get(url)
            self.assertRedirectsToLogin(response)
