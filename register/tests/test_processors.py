import datetime

from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings
from django.utils.timezone import now

from mock import Mock, patch
from civil_registry.models import Citizen
from civil_registry.tests.factories import CitizenFactory

from libya_elections import constants
from libya_elections.constants import OUTGOING
from libya_elections.utils import get_random_number_string
from register.tests.factories import RegistrationFactory, SMSFactory, \
    RegistrationCenterFactory
from text_messages.models import MessageText
from text_messages.utils import get_message
from voting.tests.factories import RegistrationPeriodFactory

from .base import LibyaTest, LibyaRapidTest, PAST_DAY, FUTURE_DAY
from .. import models
from ..processors import Result, process_registration_lookup, process_registration_request


ONE_SECOND = datetime.timedelta(seconds=1)


class RegisterProcessorTest(LibyaTest):

    def setUp(self):
        self.sms = SMSFactory()
        self.citizen = CitizenFactory(national_id=219782058018)
        self.center = RegistrationCenterFactory()
        RegistrationCenterFactory(center_id=self.center.center_id, deleted=True)
        self.mock_response = Mock()
        self.reg_period = RegistrationPeriodFactory(start_time=PAST_DAY, end_time=FUTURE_DAY)

    def test_invalid_registration_center(self):
        # No such registration center
        result = process_registration_request(
            center_id=121212,
            national_id=self.citizen.national_id,
            sms=self.sms
        )
        self.assertEqual(result.message_code, constants.RESPONSE_CENTER_ID_INVALID)

    def test_no_reg_registration_center(self):
        # If a center doesn't support registrations, don't allow one
        no_reg_center = self.center
        no_reg_center.reg_open = False
        no_reg_center.save()
        # try to register
        result = process_registration_request(
            center_id=no_reg_center.center_id,
            national_id=self.citizen.national_id,
            sms=self.sms
        )
        self.assertEqual(result.message_code, constants.RESPONSE_CENTER_ID_INVALID)

    def test_removing_reg_capability_doesnt_affect_registrations(self):
        registration = RegistrationFactory(archive_time=None)
        # Disallow registrations
        registration.registration_center.reg_open = False
        registration.registration_center.save()
        # Registration is still there
        regs = models.Registration.objects.filter(
            registration_center=registration.registration_center)
        self.assertEqual(len(regs), 1)
        # But report queries will ignore such registrations

    def test_can_reregister_after_reg_capability_removed(self):
        registration = RegistrationFactory(archive_time=None)
        RegistrationFactory(archive_time=None, deleted=True)
        # Inactivate the center
        registration.registration_center.reg_open = False
        registration.registration_center.save()
        # Process a new registration
        result = process_registration_request(
            center_id=self.center.center_id,
            national_id=registration.citizen.national_id,
            sms=registration.sms
        )
        # We returned the 'successful center change' message
        self.assertEqual(result.message_code, constants.MESSAGE_1)
        # Only 1 registration present
        regs = models.Registration.objects.filter(citizen=registration.citizen)
        self.assertEqual(len(regs), 1)

    def test_invalid_nid_not_found(self):
        result = process_registration_request(
            sms=self.sms,
            national_id=11111111,
            center_id=self.center.center_id
        )
        self.assertEqual(result.message_code, constants.RESPONSE_NID_INVALID)

    @patch.object(Citizen, 'is_eligible')
    def test_not_eligible(self, mock_is_eligible):
        # Citizen.is_eligible returns False
        nid = 11111111
        self.assertFalse(Citizen.objects.filter(national_id=nid).exists())
        last_year = now().year - 1
        CitizenFactory(**{
            "national_id": nid,
            "family_name": "\u0639\u0645\u0631",
            "first_name": "\u0646\u0648\u0631\u064a\u0629",
            "birth_date": datetime.date(last_year, 9, 16),
            "gender": constants.MALE
        })
        mock_is_eligible.return_value = False
        result = process_registration_request(
            sms=self.sms,
            national_id=nid,
            center_id=self.center.center_id
        )
        self.assertEqual(result.message_code, constants.RESPONSE_NID_INVALID)

    def test_valid_no_conflict_local(self):
        result = process_registration_request(
            sms=self.sms,
            national_id=self.citizen.national_id,
            center_id=self.center.center_id
        )
        # no new citizen instance was created
        citizens = Citizen.objects.filter(pk=self.citizen.pk)
        self.assertEqual(citizens.count(), 1)
        # There should be only one registration for this new user
        registrations = models.Registration.objects.filter(citizen=citizens[0])
        self.assertEqual(1, registrations.count())
        # We tell the user that everything went well
        self.assertEqual(result.message_code, constants.RESPONSE_VALID_REGISTRATION)

    def test_user_already_registered(self):
        """New registration for same user from different phone"""
        # Must be unlocked to update reg from different phone
        registration = models.Registration(
            citizen=self.citizen,
            registration_center=self.center,
            archive_time=None,
            sms=self.sms,
            unlocked_until=now() + datetime.timedelta(hours=1),
        )
        registration.save()
        new_sms = SMSFactory()
        result = process_registration_request(
            sms=new_sms,
            national_id=self.citizen.national_id,
            center_id=self.center.center_id
        )
        # There should be only one registration for this new user
        new_registration = models.Registration.objects.get(citizen=self.citizen)
        # The registering phone number was updated
        self.assertEqual(new_sms.from_number, new_registration.sms.from_number)
        # We tell the user that everything went well
        self.assertEqual(result.message_code, constants.MESSAGE_1)

    @override_settings(MAX_REGISTRATIONS_PER_PHONE=1)
    def test_phone_has_max_registrations(self):
        number = '12345678'
        RegistrationFactory(sms__from_number=number, archive_time=None)
        new_sms = SMSFactory(from_number=number)
        result = process_registration_request(
            sms=new_sms,
            national_id=self.citizen.national_id,
            center_id=self.center.center_id
        )
        self.assertEqual(result.message_code, constants.TOO_MANY_REGISTRATIONS_ON_PHONE)
        with self.assertRaises(models.Registration.DoesNotExist):
            models.Registration.objects.get(citizen=self.citizen)

    @override_settings(MAX_REGISTRATIONS_PER_PHONE=2)
    def test_phone_reaches_max_registrations(self):
        number = '12345678'
        RegistrationFactory(sms__from_number=number, archive_time=None)
        new_sms = SMSFactory(from_number=number)
        result = process_registration_request(
            sms=new_sms,
            national_id=self.citizen.national_id,
            center_id=self.center.center_id
        )
        self.assertEqual(result.message_code, constants.AT_MAXIMUM_REGISTRATIONS_ON_PHONE)
        models.Registration.objects.get(citizen=self.citizen)

    @override_settings(MAX_REGISTRATIONS_PER_PHONE=3)
    def test_phone_reaches_only_one_more(self):
        number = '12345678'
        RegistrationFactory(sms__from_number=number, archive_time=None)
        new_sms = SMSFactory(from_number=number)
        result = process_registration_request(
            sms=new_sms,
            national_id=self.citizen.national_id,
            center_id=self.center.center_id
        )
        self.assertEqual(result.message_code, constants.ONE_MORE_REGISTRATION_ON_PHONE)
        models.Registration.objects.get(citizen=self.citizen)

    def test_update_registration(self):
        registration = models.Registration(
            citizen=self.citizen,
            archive_time=None,
            sms=self.sms,
            registration_center=self.center
        )
        registration.save()
        # same number sends new sms
        new_sms = SMSFactory(from_number=self.sms.from_number)
        new_center = RegistrationCenterFactory()
        result = process_registration_request(
            sms=new_sms,
            national_id=self.citizen.national_id,
            center_id=new_center.center_id
        )
        # There should be only one registration for this user and should have been updated
        registrations = models.Registration.objects.filter(citizen=self.citizen)
        self.assertEqual(1, registrations.count())
        self.assertEqual(registrations[0].registration_center, new_center)
        # We tell the user that everything went well
        self.assertEqual(result.message_code, constants.MESSAGE_1)

    def test_register_after_unconfirmed_registrations(self):
        # We might have unconfirmed registrations due to previous changes.
        # Create 2 registrations for this Citizen
        RegistrationFactory(citizen=self.citizen, archive_time=now())
        RegistrationFactory(citizen=self.citizen, archive_time=now(), deleted=True)
        RegistrationFactory(citizen=self.citizen, archive_time=None, deleted=True)
        RegistrationFactory(citizen=self.citizen, archive_time=None)
        # Process another registration update
        process_registration_request(
            sms=SMSFactory(),
            national_id=self.citizen.national_id,
            center_id=self.center.center_id
        )
        # There should be only one confirmed registration
        registrations = models.Registration.objects.filter(citizen=self.citizen)
        self.assertEqual(1, registrations.count())

    def test_copy_registration_center(self):
        """test that people can't register against a copy center"""
        copy_center = RegistrationCenterFactory()
        copy_center.copy_of = self.center
        copy_center.save()
        # try to register
        result = process_registration_request(
            center_id=copy_center.center_id,
            national_id=self.citizen.national_id,
            sms=self.sms
        )
        self.assertEqual(result.message_code, constants.RESPONSE_CENTER_ID_INVALID)


class EndToEndTests(LibyaRapidTest):
    def setUp(self):
        self.fields = {'to_addr': settings.REGISTRATION_SHORT_CODE}
        self.conn = self.create_connection()
        self.reg_period = RegistrationPeriodFactory(start_time=PAST_DAY, end_time=FUTURE_DAY)

    def test_can_repeat_reg(self):
        # User can send multiple messages from the same phone number for the
        # same voting center.
        citizen = CitizenFactory()
        center1 = RegistrationCenterFactory()
        # Message #1 - original registration
        self.receive("%s %s" % (citizen.national_id, center1.center_id), self.conn,
                     fields=self.fields)
        # Citizen should be registered
        reg = models.Registration.objects.get(citizen=citizen)
        self.assertEqual(center1, reg.registration_center)
        self.assertEqual(constants.RESPONSE_VALID_REGISTRATION, self.get_last_response_code())

        # Repeat - message 2
        self.receive("%s %s" % (citizen.national_id, center1.center_id), self.conn,
                     fields=self.fields)
        # Citizen should be registered
        reg = models.Registration.objects.get(citizen=citizen)
        self.assertEqual(center1, reg.registration_center)
        # Repeated reg
        self.assertEqual(constants.MESSAGE_1, self.get_last_response_code())
        self.receive("%s %s" % (citizen.national_id, center1.center_id), self.conn,
                     fields=self.fields)
        self.assertEqual(constants.MESSAGE_1, self.get_last_response_code())

    def test_can_change_reg(self):
        # User can send multiple messages from the same phone number and change
        # their voting center.
        citizen = CitizenFactory()
        center1 = RegistrationCenterFactory()
        center2 = RegistrationCenterFactory()
        center3 = RegistrationCenterFactory()
        self.receive("%s %s" % (citizen.national_id, center1.center_id), self.conn,
                     fields=self.fields)
        # Citizen should be registered
        reg = models.Registration.objects.get(citizen=citizen)
        self.assertEqual(center1, reg.registration_center)
        # Initial registration
        self.assertEqual(constants.RESPONSE_VALID_REGISTRATION, self.get_last_response_code())

        # They change their mind and register for a different center
        self.receive("%s %s" % (citizen.national_id, center2.center_id), self.conn,
                     fields=self.fields)
        # Citizen should be registered
        reg2 = models.Registration.objects.get(citizen=citizen)
        self.assertEqual(reg.pk, reg2.pk)
        # But at a new center
        self.assertEqual(center2, reg2.registration_center)
        self.assertEqual(constants.MESSAGE_1, self.get_last_response_code())
        # There's an archive
        archive = models.Registration.objects.archived().get(citizen=citizen)
        self.assertEqual(archive.archive_time, reg2.creation_date)
        # The archive has the previous data
        self.assertEqual(center1, archive.registration_center)

        # They change their mind and register for a different center
        self.receive("%s %s" % (citizen.national_id, center3.center_id), self.conn,
                     fields=self.fields)
        # Citizen should be registered
        reg3 = models.Registration.objects.get(citizen=citizen)
        # But at a new center
        self.assertEqual(center3, reg3.registration_center)
        self.assertEqual(constants.MESSAGE_4, self.get_last_response_code())
        # most recent archive has the previous data
        archive = models.Registration.objects.archived().filter(citizen=citizen)\
            .order_by('-archive_time').first()
        self.assertEqual(center2, archive.registration_center)

    def test_user_can_change_from_inactivated_center(self):
        # User should be able to change registration center, even if previous center was
        # inactivated.
        # Create a registration and inactivate the center
        citizen = CitizenFactory()
        inactivated_center = RegistrationCenterFactory()
        self.receive("%s %s" % (citizen.national_id, inactivated_center.center_id), self.conn,
                     fields=self.fields)
        inactivated_center.reg_open = False
        inactivated_center.save()
        # User registers at a new center
        new_center = RegistrationCenterFactory()
        self.receive("%s %s" % (citizen.national_id, new_center.center_id), self.conn,
                     fields=self.fields)
        self.assertEqual(constants.MESSAGE_1, self.get_last_response_code())
        new_reg = models.Registration.objects.get(citizen=citizen)
        self.assertEqual(new_reg.registration_center, new_center)


class TestResultClass(LibyaTest):
    def setUp(self):
        MessageText.objects.create(
            number=999,
            msg_en='Test message',
            enhanced_en='Enhanced',
        )
        self.last_timestamp = now()

    def add_message(self, phone_number, message_code):
        """
        Add a fake outgoing SMS message as if we sent it, to the given
        phone number, with the given message code.
        Set the dates each time to at least 1 second later than any
        previous date.
        """
        self.last_timestamp += ONE_SECOND
        SMSFactory(
            message_code=message_code,
            to_number=phone_number,
            direction=OUTGOING,
            creation_date=self.last_timestamp,
            modification_date=self.last_timestamp,
        )

    def test_invalid_message_code(self):
        # Raises ValueError if we pass a non-existing message code
        MessageText.objects.filter(number=999).delete()
        with self.assertRaises(ValueError):
            Result("", 999)

    def test_no_context(self):
        # Test it works without passing a context
        # This also tests that with no outgoing messages, we don't use
        # the enhanced message
        r = Result("", 999)
        self.assertEqual(get_message(999).msg, r.message)

    def test_with_context(self):
        # Messages can be formatted with context vars
        m = get_message(999)
        m.msg_en = 'one: {one} two: {two} three: {three}'
        m.save()
        r = Result("", 999, dict(one=1, two=2, three=3))
        self.assertEqual('one: 1 two: 2 three: 3', r.message)

    def test_context_missing_var(self):
        # If a message has one var we don't have values for, we still carry on
        # we just leave the value blank
        m = get_message(999)
        m.msg_en = 'one: {one} two: {two} three: {three}'
        m.save()
        r = Result("", 999, dict(one=1, two=2))
        self.assertEqual('one: 1 two: 2 three: ', r.message)

    def test_context_two_missing_vars(self):
        # If a message has two vars we don't have values for, we punt
        # (just use the unformatted message)
        m = get_message(999)
        m.msg_en = 'one: {one} two: {two} three: {three}'
        m.save()
        r = Result("", 999, dict(one=1))
        self.assertEqual(m.msg_en, r.message)

    def test_one_message_not_enhanced(self):
        # If there's an enhanced message available, but only one
        # outgoing message with the current error code, don't use
        # enhanced
        self.add_message("411", 999)
        r = Result("411", 999)
        self.assertEqual(get_message(999).msg, r.message)

    def test_two_messages_not_enhanced(self):
        # If there's an enhanced message available, but only two
        # messages with the current error code, don't use
        # enhanced
        self.add_message("411", 999)
        self.add_message("411", 999)
        r = Result("411", 999)
        self.assertEqual(get_message(999).msg, r.message)

    def test_three_messages_enhanced(self):
        # If there's an enhanced message available, and three
        # messages with the current error code, use
        # enhanced
        self.add_message("411", 999)
        self.add_message("411", 999)
        self.add_message("411", 999)
        r = Result("411", 999)
        self.assertEqual(get_message(999).enhanced, r.message)

    def test_mixed_messages(self):
        # If there are at least three messages with the same code,
        # but not the last three, then don't use enhanced.
        self.add_message("411", 999)
        self.add_message("411", constants.MESSAGE_INCORRECT)
        self.add_message("411", 999)
        self.add_message("411", 999)
        r = Result("411", 999)
        self.assertEqual(get_message(999).msg, r.message)

    def test_mixed_phones(self):
        # If the last three messages were the same code, but they weren't
        # all to our phone number, then don't use enhanced
        self.add_message("411", 999)
        self.add_message("410", 999)
        self.add_message("411", 999)
        r = Result("411", 999)
        self.assertEqual(get_message(999).msg, r.message)

    def test_not_last_three(self):
        # If there were three in a row, but not the last three,
        # don't use enhanced
        self.add_message("411", 999)
        self.add_message("411", 999)
        self.add_message("411", 999)
        self.add_message("411", constants.MESSAGE_INCORRECT)
        r = Result("411", 999)
        self.assertEqual(get_message(999).msg, r.message)


class TestRegistrationLookUp(TestCase):
    def setUp(self):
        self.citizen = CitizenFactory()
        self.good_nid = self.citizen.national_id
        self.bad_nid = long(get_random_number_string(length=constants.NID_LENGTH))
        self.nid_without_citizen = long(get_random_number_string(length=constants.NID_LENGTH))
        self.sms = SMSFactory()

    def test_nlid_does_not_exist(self):
        # If no such national ID, then return VOTER_QUERY_NOT_FOUND.
        result = process_registration_lookup(self.bad_nid, self.sms)
        self.assertEqual(result.message_code, constants.VOTER_QUERY_NOT_FOUND)

    def test_citizen_is_not_registered(self):
        # Looking up a citizen's registration for a citizen who has not yet registered
        # should inform VOTER_QUERY_NOT_REGISTERED
        result = process_registration_lookup(self.good_nid, self.sms)
        self.assertEqual(result.message_code, constants.VOTER_QUERY_NOT_REGISTERED)

    def test_citizen_has_no_confirmed_registrations(self):
        # A citizen with unconfirmed registration(s) should be informed that he
        # is not registered (VOTER_QUERY_NOT_REGISTERED)
        RegistrationFactory(citizen=self.citizen, archive_time=now())
        result = process_registration_lookup(self.good_nid, self.sms)
        self.assertEqual(result.message_code, constants.VOTER_QUERY_NOT_REGISTERED)

    def test_citizen_has_mutiple_unconfirmed_registration(self):
        # A citizen with multiple unconfirmed registration is treated the same as
        # one with 1 unconfirmed registrations
        RegistrationFactory(citizen=self.citizen)
        RegistrationFactory(citizen=self.citizen)
        result = process_registration_lookup(self.good_nid, self.sms)
        self.assertEqual(result.message_code, constants.VOTER_QUERY_NOT_REGISTERED)

    def test_citizen_is_registered(self):
        # Citizen correctly registered will be informed about the Election Center
        # where they are currently registered to vote.
        RegistrationFactory(citizen=self.citizen, archive_time=None)
        result = process_registration_lookup(self.good_nid, self.sms)
        self.assertEqual(result.message_code, constants.VOTER_QUERY_REGISTERED_AT)
