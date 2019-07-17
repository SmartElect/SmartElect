# -*- coding: utf-8 -*-
import datetime
from unittest import skip

from django.conf import settings
from django.db import IntegrityError
from django.test import TestCase, override_settings, TransactionTestCase
from django.utils.encoding import force_text
from django.utils.timezone import now
from django.core.exceptions import ValidationError

from factory import create_batch

from civil_registry.tests.factories import CitizenFactory
from libya_elections.constants import INCOMING, OUTGOING, SPLIT_CENTER_SUBCONSTITUENCY_ID, \
    CENTER_ID_LENGTH, NO_NAMEDTHING
from register.models import Blacklist, Registration, SMS, Whitelist, \
    RegistrationCenter, SubConstituency, Constituency, Office
from register.tests.factories import SMSFactory, RegistrationCenterFactory, \
    BlacklistFactory, WhitelistFactory, RegistrationFactory, SubConstituencyFactory
from register.utils import is_blacklisted, is_whitelisted
from register.tests.base import LibyaTest
from text_messages.models import MessageText


class ConstituencyTest(LibyaTest):
    def test_no_named_constituency(self):
        self.assertTrue(Constituency.objects.filter(id=NO_NAMEDTHING).exists())


class SubConstituencyTest(LibyaTest):
    def test_no_named_and_split_subcon(self):
        self.assertTrue(SubConstituency.objects.filter(id=NO_NAMEDTHING).exists())
        self.assertTrue(SubConstituency.objects.filter(id=SPLIT_CENTER_SUBCONSTITUENCY_ID).exists())


class OfficeTest(LibyaTest):
    def test_no_named_office(self):
        self.assertTrue(Office.objects.filter(id=NO_NAMEDTHING).exists())


class BlacklistCacheTest(LibyaTest):

    def test_cache_is_used(self):
        BlacklistFactory(phone_number='1')
        # second time we get the blacklist, we should do zero queries
        self.assertNumQueries(1, is_blacklisted, '1')
        self.assertNumQueries(0, is_blacklisted, '1')

    def test_cache_resets_after_new_entry(self):
        BlacklistFactory(phone_number='1')
        # freshly created blacklist has '1' in it
        self.assertTrue(is_blacklisted('1'))
        # add a number to the blacklist
        BlacklistFactory(phone_number='2')
        # '2' should now be in the blacklist
        self.assertTrue(is_blacklisted('2'))

    def test_numbers_can_be_removed_from_blacklist(self):
        number = BlacklistFactory(phone_number='1')
        self.assertTrue(is_blacklisted('1'))
        number.deleted = True
        number.save()
        self.assertFalse(is_blacklisted('1'))
        Blacklist.objects.filter(pk=number.pk).delete()
        self.assertFalse(is_blacklisted('1'))


class WhitelistCacheTest(LibyaTest):

    def test_cache_is_used(self):
        WhitelistFactory(phone_number='1')
        # second time we get the whitelist, we should do zero queries
        self.assertNumQueries(1, is_whitelisted, '1')
        self.assertNumQueries(0, is_whitelisted, '1')

    def test_cache_is_not_used_if_number_not_on_list(self):
        # whitelist is empty
        self.assertNumQueries(1, is_whitelisted, '1')
        self.assertNumQueries(1, is_whitelisted, '1')

    def test_numbers_can_be_removed_from_whitelist(self):
        WhitelistFactory(phone_number='1')
        self.assertTrue(is_whitelisted('1'))
        Whitelist.objects.all().delete()
        self.assertFalse(is_whitelisted('1'))


# We were skipping until https://code.djangoproject.com/ticket/23727 was fixed. That is fixed now,
# but keepdb is still broken with TransactionTestCase, so keep skipping until
# https://code.djangoproject.com/ticket/25251 is fixed.
@skip("until https://code.djangoproject.com/ticket/25251 is fixed")
class BlackAndWhitelistUniquenessTest(TransactionTestCase):
    """Ensures that black & whitelist numbers must be unique as long as they're not deleted.

    This has to be a TransactionTestCase because it raises an IntegrityError which breaks
    the transaction created by the ordinary Django TestCase.
    """

    # https://docs.djangoproject.com/en/1.8/topics/testing/overview/#test-case-serialized-rollback
    serialized_rollback = True

    def test_blacklist_uniqueness_is_enforced(self):
        number = BlacklistFactory(phone_number='99')
        with self.assertRaises(IntegrityError):
            BlacklistFactory(phone_number='99')
        self.assertEqual(Blacklist.objects.filter(phone_number='99').count(), 1)
        number.deleted = True
        number.save()
        BlacklistFactory(phone_number='99')
        self.assertEqual(Blacklist.objects.filter(phone_number='99').count(), 1)

    def test_whitelist_uniqueness_is_enforced(self):
        number = WhitelistFactory(phone_number='99')
        with self.assertRaises(IntegrityError):
            WhitelistFactory(phone_number='99')
        self.assertEqual(Whitelist.objects.filter(phone_number='99').count(), 1)
        number.deleted = True
        number.save()
        WhitelistFactory(phone_number='99')
        self.assertEqual(Whitelist.objects.filter(phone_number='99').count(), 1)


class RegistrationTest(TestCase):
    def test_change_period(self):
        reg = Registration()
        self.assertFalse(reg.unlocked)
        reg.unlocked_until = now() + datetime.timedelta(hours=1)
        self.assertTrue(reg.unlocked)
        reg.unlocked_until = now() - datetime.timedelta(hours=1)
        self.assertFalse(reg.unlocked)

    @override_settings(MAX_REGISTRATIONS_PER_PHONE=2)
    def test_phone_has_maximum_registrations(self):
        phone_number = '12345'
        reg = RegistrationFactory(sms__from_number=phone_number, archive_time=None)
        self.assertFalse(reg.phone_has_maximum_registrations)
        RegistrationFactory(sms__from_number=phone_number, archive_time=None)
        self.assertTrue(reg.phone_has_maximum_registrations)

    def test_unique_registration(self):
        # Undeleted, confirmed registrations must be unique on citizen
        citizen = CitizenFactory()
        RegistrationFactory(citizen=citizen, deleted=False, archive_time=None)
        RegistrationFactory(citizen=citizen, deleted=True)
        RegistrationFactory(citizen=citizen, archive_time=now())
        with self.assertRaises(IntegrityError):
            RegistrationFactory(citizen=citizen, deleted=False, archive_time=None)


class RegistrationArchivingTest(TestCase):
    def setUp(self):
        # Start with a confirmed registration
        self.reg = RegistrationFactory(archive_time=None)

    def test_save_with_archive_version(self):
        orig_change_count = self.reg.change_count
        self.reg.change_count = 99
        self.reg.save_with_archive_version()
        # See what's in the DB for this record
        cur_reg = Registration.objects.get(citizen=self.reg.citizen)
        self.assertEqual(99, cur_reg.change_count)
        # See if there's an archive record now
        archive = Registration.objects.archived().get(citizen=self.reg.citizen)
        self.assertNotEqual(archive.pk, self.reg.pk)
        self.assertEqual(orig_change_count, archive.change_count)
        self.assertTrue(archive.archive_time <= now())
        # And the times match
        self.assertEqual(archive.archive_time, cur_reg.creation_date)


class RegistrationCenterTest(TestCase):

    def test_copy_of_copy_fails(self):
        """test that a copy center can't be a copy of another copy center"""
        original_center = RegistrationCenterFactory()
        copy_center = RegistrationCenterFactory(copy_of=original_center)
        copy_copy_center = RegistrationCenterFactory.build(copy_of=copy_center)

        with self.assertRaises(ValidationError) as cm:
            copy_copy_center.clean()
        self.assertEqual(cm.exception.message, 'A copy centre cannot copy another copy centre.')

    def test_max_copies_per_center_limit(self):
        """test that register.models.N_MAX_COPY_CENTERS is respected"""
        original_center = RegistrationCenterFactory()
        create_batch(RegistrationCenterFactory, settings.N_MAX_COPY_CENTERS,
                     copy_of=original_center)

        copy_center = RegistrationCenterFactory.build(copy_of=original_center)
        with self.assertRaises(ValidationError) as cm:
            copy_center.clean()
        msg = 'Copy centre already has the maximum number of copies ({n_max}).'
        self.assertEqual(cm.exception.message, msg.format(n_max=settings.N_MAX_COPY_CENTERS))

    def test_all_related_by_copy(self):
        """exercise all_related_by_copy()"""
        original_center = RegistrationCenterFactory()
        # Create copies with center ids in unsorted order to verify all_related_by_copy() sorts
        # as promised.
        copies = []
        for center_id in (77777, 22222, 66666, 33333, 55555):
            copy_center = RegistrationCenterFactory(center_id=center_id, copy_of=original_center)
            copies.append(copy_center)

        copies.sort(key=lambda center: center.center_id)

        # test getting centers related to the original (parent) center
        actual_copies = original_center.all_related_by_copy()

        # original centers is always first in the returned list
        self.assertEqual(original_center, actual_copies[0])
        expected = copies
        actual = actual_copies[1:]
        self.assertEqual(expected, actual)

        # test getting centers related to one of the copies
        a_copy = copies[1]
        actual_copies = a_copy.all_related_by_copy()

        # original centers is always first in the returned list
        self.assertEqual(original_center, actual_copies[0])
        # expected remains the same as above
        actual = actual_copies[1:]
        self.assertEqual(expected, actual)

        # test that all_related_by_copy() doesn't return deleted centers
        a_copy = copies[1]
        a_copy.deleted = True
        a_copy.save()
        actual_copies = original_center.all_related_by_copy()
        expected = [copies[0]] + copies[2:]
        actual = actual_copies[1:]
        self.assertEqual(expected, actual)

        # test that all_related_by_copy() is the identity function for non-copy centers
        copyless_center = RegistrationCenterFactory()
        actual_copies = copyless_center.all_related_by_copy()
        self.assertEqual(copyless_center, actual_copies[0])
        self.assertEqual(len(actual_copies), 1)

    def test_copy_read_only(self):
        """test that copy centers are uneditable once created."""
        copy_center = RegistrationCenterFactory(center_type=RegistrationCenter.Types.COPY)

        with self.assertRaises(ValidationError) as cm:
            copy_center.clean()
        self.assertEqual(force_text(cm.exception.message), 'Copy centres are read-only.')

    def test_copy_center_must_remain_copy_center(self):
        """test that a copy center can't be made into a non-copy center"""
        original_center = RegistrationCenterFactory()
        copy_center = RegistrationCenterFactory(copy_of=original_center)
        copy_center.copy_of = None

        with self.assertRaises(ValidationError) as cm:
            copy_center.clean()
        self.assertEqual(force_text(cm.exception.message), 'Copy centres are read-only.')

    def test_noncopy_center_cannot_become_copy_center(self):
        """test that a non-copy center can't be made into a copy center"""
        original_center = RegistrationCenterFactory()
        copy_center = RegistrationCenterFactory()

        copy_center.copy_of = original_center
        copy_center.center_type = RegistrationCenter.Types.COPY

        with self.assertRaises(ValidationError) as cm:
            copy_center.clean()
        self.assertEqual(force_text(cm.exception.message),
                         'A centre may not be changed to a copy centre.')

    def test_copy_center_requires_copy_type(self):
        """test that a copy center must have the correct type"""
        original_center = RegistrationCenterFactory()
        copy_center = RegistrationCenterFactory.build(copy_of=original_center)
        copy_center.center_type = RegistrationCenter.Types.GENERAL

        with self.assertRaises(ValidationError) as cm:
            copy_center.clean()
        self.assertEqual(cm.exception.message, 'Copy centre type must be "copy".')

    def test_copy_center_requires_copy_info(self):
        """test that a center with copy type requires copy_of info"""
        copy_center = RegistrationCenterFactory.build(center_type=RegistrationCenter.Types.COPY)
        copy_center.copy_of = None

        with self.assertRaises(ValidationError) as cm:
            copy_center.clean()
        self.assertEqual(cm.exception.message,
                         'Centre type "copy" requires copy centre information.')

    def test_delete_all_copy_centers(self):
        """test RegistrationCenterManager.delete_all_copy_centers()"""
        original_center = RegistrationCenterFactory()
        copy_center = RegistrationCenterFactory(copy_of=original_center)

        RegistrationCenter.objects.delete_all_copy_centers()

        # Ensure the copy center is gone...
        with self.assertRaises(RegistrationCenter.DoesNotExist):
            RegistrationCenter.objects.get(pk=copy_center.id)

        # ...but it still exists if you know where to look.
        self.assertEqual(copy_center,
                         RegistrationCenter.objects.unfiltered().get(pk=copy_center.id))

    def test_split_center_ok(self):
        """test that a split center can be created"""
        split_center_subcon, unused = \
            SubConstituency.objects.get_or_create(id=SPLIT_CENTER_SUBCONSTITUENCY_ID)

        center = RegistrationCenterFactory.build(center_type=RegistrationCenter.Types.SPLIT,
                                                 subconstituency=split_center_subcon)
        # This should not raise an error
        center.clean()

    def test_split_center_must_use_split_subcon(self):
        """test that a split center must be associated with the correct subcon"""
        some_random_subcon = SubConstituencyFactory()
        center = RegistrationCenterFactory.build(center_type=RegistrationCenter.Types.SPLIT,
                                                 subconstituency=some_random_subcon)
        with self.assertRaises(ValidationError) as cm:
            center.clean()
        msg = "Split centers must be associated with subconstituency {}."
        msg = msg.format(SPLIT_CENTER_SUBCONSTITUENCY_ID)
        self.assertEqual(cm.exception.message, msg)

    def test_nonsplit_center_cannot_use_split_subcon(self):
        """test that a non-split center cannot be associated with the split-specific subcon"""
        split_center_subcon, unused = \
            SubConstituency.objects.get_or_create(id=SPLIT_CENTER_SUBCONSTITUENCY_ID)
        center = RegistrationCenterFactory.build(center_type=RegistrationCenter.Types.GENERAL,
                                                 subconstituency=split_center_subcon)
        with self.assertRaises(ValidationError) as cm:
            center.clean()
        msg = "Only split centers may be associated with subconstituency {}."
        msg = msg.format(SPLIT_CENTER_SUBCONSTITUENCY_ID)
        self.assertEqual(cm.exception.message, msg)

    def test_sort_order(self):
        """test that centers are sorted by center_id"""
        # Explicitly create with out-of-order center ids
        center_ids = ['4', '7', '2', '1', '8']
        # Make IDs like 44444, etc.
        center_ids = [int(center_id * CENTER_ID_LENGTH) for center_id in center_ids]

        for center_id in center_ids:
            RegistrationCenterFactory(center_id=center_id)
        center_ids.sort()

        actual_center_ids = [
            center.center_id
            for center in RegistrationCenter.objects.all()
        ]
        self.assertEqual(center_ids, actual_center_ids)


class SMSTest(TestCase):
    def test_anonymize_incoming(self):
        citizen = CitizenFactory()
        sms = SMSFactory(
            from_number='7',
            to_number='6',
            message='Hey man let\'s vote',
            citizen=citizen,
            uuid='278348723478234',
            direction=INCOMING,
            need_to_anonymize=True,
        )
        sms.save()
        SMS.objects.filter(pk=sms.pk).anonymize()
        sms = SMS.objects.get(pk=sms.pk)
        # only anonymize the 'from' number for incoming
        self.assertEqual('', sms.from_number)
        self.assertEqual('6', sms.to_number)
        self.assertEqual('', sms.message)
        self.assertIsNone(sms.citizen)
        self.assertEqual('', sms.uuid)
        self.assertFalse(sms.need_to_anonymize)

    def test_anonymize_outgoing(self):
        citizen = CitizenFactory()
        sms = SMSFactory(
            from_number='7',
            to_number='6',
            message='Hey man let\'s vote',
            citizen=citizen,
            uuid='278348723478234',
            direction=OUTGOING,
            need_to_anonymize=True,
        )
        sms.save()
        SMS.objects.filter(pk=sms.pk).anonymize()
        sms = SMS.objects.get(pk=sms.pk)
        # only anonymize the 'to' number for outgoing
        self.assertEqual('7', sms.from_number)
        self.assertEqual('', sms.to_number)
        self.assertEqual('', sms.message)
        self.assertIsNone(sms.citizen)
        self.assertEqual('', sms.uuid)
        self.assertFalse(sms.need_to_anonymize)

    def test_get_message_code_display(self):
        """SMS.get_message_code_display returns label of corresponding MessageText object."""
        msg = MessageText.objects.create(number=23, label='TWENTY_THREE')
        sms = SMSFactory(message_code=msg.number)
        self.assertEqual(msg.label, sms.get_message_code_display())

    def test_get_message_code_display_for_obsolete_message(self):
        """If MessageText object gets deleted, we should not fail."""
        msg = MessageText.objects.create(number=23, label='TWENTY_THREE')
        sms = SMSFactory(message_code=msg.number)
        msg.delete()
        self.assertEqual('Obsolete message code: 23', sms.get_message_code_display())
