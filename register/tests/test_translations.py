# -*- coding: utf-8 -*-
import datetime
from unittest.mock import patch

from django.conf import settings
from django.test.utils import override_settings

from civil_registry.tests.factories import CitizenFactory
from libya_elections import constants
from libya_elections.utils import get_random_number_string
from libya_elections.phone_numbers import get_random_phone_number
from polling_reports.models import StaffPhone
from register.tests.factories import RegistrationFactory, RegistrationCenterFactory, \
    SMSFactory
from voting.tests.factories import RegistrationPeriodFactory

from .. import utils
from ..tests.base import LibyaRapidTest, TranslationTest, FUTURE_DAY, PAST_DAY


@override_settings(OUTGOING_MESSAGE_LANGUAGE='ar',
                   LANGUAGE_CODE='en')
@patch.object(utils, "tool_1_enabled")
class ResponseTest(TranslationTest, LibyaRapidTest):
    # Test response messages (Arabic)

    def setUp(self):
        self.number = "919-999-9999"
        self.center = RegistrationCenterFactory()
        self.conn = self.create_connection(data={'identity': self.number})
        self.citizen = CitizenFactory()
        self.good_nid = self.citizen.national_id
        self.bad_nid = get_random_number_string(length=constants.NID_LENGTH)
        self.short_nid = get_random_number_string(length=constants.NID_LENGTH - 1)
        self.good_center_id = self.center.center_id
        self.bad_center_id = get_random_number_string(length=constants.CENTER_ID_LENGTH)
        self.long_center_id = get_random_number_string(length=constants.CENTER_ID_LENGTH + 1)
        self.fields = {'to_addr': settings.REGISTRATION_SHORT_CODE}
        RegistrationPeriodFactory(start_time=PAST_DAY, end_time=FUTURE_DAY)

    def test_garbage(self, registration_open):
        self.receive("PING", self.conn, fields=self.fields)
        expected = self.translate(constants.MESSAGE_INCORRECT)  # arabic
        self.assertEqual(self.get_last_response_message(), expected)

    def test_garbage_enhanced(self, registration_open):
        for i in range(1, 5):
            # last iteration should get an enhanced message
            self.receive("PING", self.conn, fields=self.fields)
        expected = self.translate(constants.MESSAGE_INCORRECT, enhanced=True)  # arabic
        self.assertEqual(self.get_last_response_message(), expected)

    def test_wrong_length_nid(self, registration_open):
        msg = "{nid}#{center}".format(nid=self.short_nid, center=self.good_center_id)
        self.receive(msg, self.conn, fields=self.fields)
        expected = self.translate(constants.RESPONSE_NID_WRONG_LENGTH)  # arabic
        self.assertEqual(self.get_last_response_message(), expected)

    def test_wrong_length_nid_enhanced(self, registration_open):
        msg = "{nid}#{center}".format(nid=self.short_nid, center=self.good_center_id)
        for i in range(1, 5):
            # last iteration should get an enhanced message
            self.receive(msg, self.conn, fields=self.fields)
        expected = self.translate(constants.RESPONSE_NID_WRONG_LENGTH, enhanced=True)  # arabic
        self.assertEqual(self.get_last_response_message(), expected)

    def test_wrong_length_center_id(self, registration_open):
        msg = "{nid}#{center}".format(nid=self.good_nid, center=self.long_center_id)
        self.receive(msg, self.conn, fields=self.fields)
        expected = self.translate(constants.RESPONSE_CENTER_ID_WRONG_LENGTH)  # arabic
        self.assertEqual(self.get_last_response_message(), expected)

    def test_wrong_length_center_id_enhanced(self, registration_open):
        msg = "{nid}#{center}".format(nid=self.good_nid, center=self.long_center_id)
        for i in range(1, 5):
            # last iteration should get an enhanced message
            self.receive(msg, self.conn, fields=self.fields)
        expected = self.translate(constants.RESPONSE_CENTER_ID_WRONG_LENGTH, enhanced=True)
        self.assertEqual(self.get_last_response_message(), expected)

    def test_wrong_length_nid_query(self, registration_open):
        msg = "{nid}".format(nid=self.short_nid)
        self.receive(msg, self.conn, fields=self.fields)
        expected = self.translate(constants.VOTER_QUERY_NID_WRONG_LENGTH)
        self.assertEqual(self.get_last_response_message(), expected)

    def test_citizen_under_18(self, registration_open):
        self.citizen.birth_date = datetime.datetime.today()
        self.citizen.save()
        msg = "{nid}#{center}".format(nid=self.good_nid, center=self.good_center_id)
        self.receive(msg, self.conn, fields=self.fields)
        expected = self.translate(constants.RESPONSE_NID_INVALID)  # arabic
        self.assertEqual(self.get_last_response_message(), expected)

    def test_center_does_not_exist(self, registration_open):
        msg = "{nid}#{center}".format(nid=self.good_nid, center=self.bad_center_id)
        self.receive(msg, self.conn, fields=self.fields)
        expected = self.translate(constants.RESPONSE_CENTER_ID_INVALID)  # arabic
        self.assertEqual(self.get_last_response_message(), expected)

    def test_nid_does_not_exist(self, registration_open):
        msg = "{nid}#{center}".format(nid=self.bad_nid, center=self.good_center_id)
        self.receive(msg, self.conn, fields=self.fields)
        expected = self.translate(constants.RESPONSE_NID_INVALID)  # arabic
        self.assertEqual(self.get_last_response_message(), expected)

    @override_settings(MAX_REGISTRATIONS_PER_PHONE=5)
    def test_good_registration(self, registration_open):
        msg = "{nid}#{center}".format(nid=self.good_nid, center=self.good_center_id)
        self.receive(msg, self.conn, fields=self.fields)
        context = {'person': str(self.citizen), 'centre': self.center.name,
                   'code': self.center.center_id}
        expected = self.translate(constants.MESSAGE_1, context=context)  # arabic
        self.assertEqual(self.get_last_response_message(), expected)

    @override_settings(MAX_REGISTRATIONS_PER_PHONE=5)
    def test_good_registration_enhanced(self, registration_open):
        msg = "{nid}#{center}".format(nid=self.good_nid, center=self.good_center_id)
        for i in range(1, 5):
            # last iteration should get an enhanced message
            self.receive(msg, self.conn, fields=self.fields)
        context = {'person': str(self.citizen), 'centre': self.center.name,
                   'code': self.center.center_id}
        expected = self.translate(constants.MESSAGE_1, context=context, enhanced=True)  # arabic
        self.assertEqual(self.get_last_response_code(), constants.MESSAGE_1)
        self.assertEqual(self.get_last_response_message(), expected)

    def test_good_update(self, registration_open):
        new_center = RegistrationCenterFactory()
        msg = "{nid}#{center}".format(nid=self.good_nid, center=self.good_center_id)
        self.receive(msg, self.conn, fields=self.fields)  # registers
        msg = "{nid}#{center}".format(nid=self.good_nid, center=new_center.center_id)
        self.receive(msg, self.conn, fields=self.fields)  # updates
        context = {'person': str(self.citizen), 'centre': new_center.name,
                   'code': new_center.center_id}
        # 1st update - message 1
        expected = self.translate(constants.MESSAGE_1, context=context)  # arabic
        self.assertEqual(self.get_last_response_message(), expected)

        # 2nd update - message 4
        msg = "{nid}#{center}".format(nid=self.good_nid, center=self.good_center_id)
        self.receive(msg, self.conn, fields=self.fields)  # updates again
        context = {'person': str(self.citizen), 'centre': new_center.name,
                   'code': self.good_center_id}
        expected = self.translate(constants.MESSAGE_4, context=context)  # arabic

        # 3rd and final update - message 5
        msg = "{nid}#{center}".format(nid=self.good_nid, center=new_center.center_id)
        self.receive(msg, self.conn, fields=self.fields)  # updates
        context = {'person': str(self.citizen), 'centre': new_center.name,
                   'code': new_center.center_id}
        expected = self.translate(constants.MESSAGE_5, context=context)  # arabic

    def test_attempt_update_wrong_from_number(self, registration_open):
        # create a valid registration
        sms = SMSFactory(from_number=self.number, citizen=self.citizen)
        RegistrationFactory(
            citizen=self.citizen,
            registration_center=self.center,
            archive_time=None,
            sms=sms)
        # try to register at a new center with a new number
        new_center = RegistrationCenterFactory()
        new_number = '919-888-8888'
        msg = "{nid}#{center}".format(nid=self.good_nid, center=new_center.center_id)
        new_conn = self.create_connection(data={'identity': new_number})
        self.receive(msg, new_conn, fields=self.fields)
        # message should have the existing number in it (not new_number)
        context = {'centre': self.center.name,
                   'number': self.number[-4:]}
        expected = self.translate(constants.MESSAGE_2, context=context)  # arabic
        self.assertEqual(self.get_last_response_message(), expected)

    def test_attempt_update_wrong_from_number_same_center(self, registration_open):
        # create a valid registration
        sms = SMSFactory(from_number=self.number, citizen=self.citizen)
        RegistrationFactory(
            citizen=self.citizen,
            registration_center=self.center,
            archive_time=None,
            sms=sms)
        # try to register at same center with a new number
        new_number = '919-888-8888'
        msg = "{nid}#{center}".format(nid=self.good_nid, center=self.center.center_id)
        new_conn = self.create_connection(data={'identity': new_number})
        self.receive(msg, new_conn, fields=self.fields)
        # message should have the existing number in it (not new_number)
        context = {'centre': self.center.name,
                   'number': self.number[-4:]}
        expected = self.translate(constants.MESSAGE_2, context=context)  # arabic
        self.assertEqual(self.get_last_response_message(), expected)


@override_settings(OUTGOING_MESSAGE_LANGUAGE='ar')
@override_settings(LANGUAGE_CODE='en')
class ResponseVoterQueryTest(TranslationTest, LibyaRapidTest):
    def setUp(self):
        self.number = get_random_phone_number()
        self.center = RegistrationCenterFactory()
        self.citizen = CitizenFactory()
        self.staffphone = StaffPhone.objects.create(phone_number=self.number,
                                                    registration_center=self.center)
        self.conn = self.create_connection(data={'identity': self.number})
        self.good_nid = self.citizen.national_id
        self.bad_nid = get_random_number_string(length=constants.NID_LENGTH)
        self.short_nid = get_random_number_string(length=constants.NID_LENGTH - 1)
        self.fields = {'to_addr': settings.REGISTRATION_SHORT_CODE}

    def test_wrong_length_nid(self):
        msg = "{nid}".format(nid=self.short_nid)
        self.receive(msg, self.conn, fields=self.fields)
        self.assertEqual(self.get_last_response_code(), constants.VOTER_QUERY_NID_WRONG_LENGTH)
        expected = self.translate(constants.VOTER_QUERY_NID_WRONG_LENGTH)  # Arabic
        self.assertEqual(self.get_last_response_message(), expected)

    def test_citizen_registered(self):
        # citizen has been registered
        RegistrationFactory(citizen=self.citizen, registration_center=self.center,
                            archive_time=None)
        # let's query for the registration
        msg = "{nid}".format(nid=self.good_nid)
        self.receive(msg, self.conn, fields=self.fields)
        self.assertEqual(self.get_last_response_code(), constants.VOTER_QUERY_REGISTERED_AT)
        context = {"person": str(self.citizen), "centre": self.center.name,
                   "code": self.center.center_id}
        expected = self.translate(constants.VOTER_QUERY_REGISTERED_AT, context)  # Arabic
        self.assertEqual(self.get_last_response_message(), expected)

    def test_citizen_not_registered(self):
        # let's query for the registration
        citizen2 = CitizenFactory()  # unregistered
        msg = "{nid}".format(nid=citizen2.national_id)
        self.receive(msg, self.conn, fields=self.fields)
        self.assertEqual(self.get_last_response_code(), constants.VOTER_QUERY_NOT_REGISTERED)
        context = {'person': str(citizen2)}
        expected = self.translate(constants.VOTER_QUERY_NOT_REGISTERED, context)  # Arabic
        self.assertEqual(self.get_last_response_message(), expected)

    def test_nlid_does_not_exist(self):
        msg = "{nid}".format(nid=self.bad_nid)
        self.receive(msg, self.conn, fields=self.fields)
        self.assertEqual(self.get_last_response_code(), constants.VOTER_QUERY_NOT_FOUND)
        expected = self.translate(constants.VOTER_QUERY_NOT_FOUND)  # Arabic
        self.assertEqual(self.get_last_response_message(), expected)
