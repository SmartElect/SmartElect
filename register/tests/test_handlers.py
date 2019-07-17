# -*- coding: utf-8 -*-
from unittest.mock import patch, Mock

from django.conf import settings
from django.test.utils import override_settings
from rapidsms.contrib.handlers import PatternHandler

from civil_registry.tests.factories import CitizenFactory
from libya_elections import constants
from libya_elections.constants import OUTGOING, INCOMING
from libya_elections.utils import get_random_number_string
from voting.tests.factories import RegistrationPeriodFactory, ElectionFactory
from .. import handlers, utils
from ..models import Registration, SMS
from ..processors import Result
from ..tests.base import LibyaRapidTest, PAST_DAY, FUTURE_DAY
from ..tests.factories import BlacklistFactory, RegistrationCenterFactory


class HandlerTest(LibyaRapidTest):
    def setUp(self):
        # lookup_connections takes any identity and creates connections.
        # It's better than create_connection because it uses 'mockbackend'
        # which keeps track of sent messages.
        self.conn = self.lookup_connections(identities=['111'])[0]
        self.good_nid = get_random_number_string(length=constants.NID_LENGTH)
        self.good_center_id = get_random_number_string(length=constants.CENTER_ID_LENGTH)
        self.fields = {'to_addr': settings.REGISTRATION_SHORT_CODE}
        self.reg_period = RegistrationPeriodFactory(start_time=PAST_DAY, end_time=FUTURE_DAY)
        self.election = ElectionFactory(polling_start_time=PAST_DAY, polling_end_time=FUTURE_DAY)

    @override_settings(MAX_REGISTRATIONS_PER_PHONE=5)
    def test_new_logic_rename_me(self):
        phone1 = get_random_number_string(length=10)
        phone2 = get_random_number_string(length=10)
        nid1 = self.good_nid
        ppc1 = self.good_center_id
        ppc2 = get_random_number_string(length=constants.CENTER_ID_LENGTH)
        ppc3 = get_random_number_string(length=constants.CENTER_ID_LENGTH)
        ppc4 = get_random_number_string(length=constants.CENTER_ID_LENGTH)
        ppc5 = get_random_number_string(length=constants.CENTER_ID_LENGTH)
        CitizenFactory(national_id=nid1)
        RegistrationCenterFactory(center_id=ppc1)
        RegistrationCenterFactory(center_id=ppc2)
        RegistrationCenterFactory(center_id=ppc3)
        RegistrationCenterFactory(center_id=ppc4)
        RegistrationCenterFactory(center_id=ppc5)
        # Each item in the test_data array is one test.
        # Each test contains one or more steps.
        # Each step contains the phone we receive a message from, the
        # registration center code in that message, the expected response,
        # and the expected registration state after that message.
        # All messages are for the same NID.
        # After each test item, the registrations are reset (deleted).

        # MSG1: you are registered, use same phone to change
        # MSG4: only one more time
        # MSG5: that was your last time

        test_data = [
            # Repeat the same registration from the same phone
            [
                (phone1, ppc1, constants.MESSAGE_1, ppc1),
                (phone1, ppc1, constants.MESSAGE_1, ppc1),
                (phone1, ppc1, constants.MESSAGE_1, ppc1),
                (phone1, ppc1, constants.MESSAGE_1, ppc1),
            ],
            # Keep trying to change your registration from the same phone
            [
                (phone1, ppc1, constants.MESSAGE_1, ppc1),
                (phone1, ppc2, constants.MESSAGE_1, ppc2),  # one change is okay
                (phone1, ppc3, constants.MESSAGE_4, ppc3),  # twice is okay but only one left
                (phone1, ppc4, constants.MESSAGE_5, ppc4),  # three is okay but last time
                (phone1, ppc3, constants.MESSAGE_6, ppc4),  # too many, sorry
                (phone1, ppc5, constants.MESSAGE_6, ppc4),  # still too many
            ],
            # Repeat the same registration from a different phone
            [
                (phone1, ppc1, constants.MESSAGE_1, ppc1),
                (phone2, ppc1, constants.MESSAGE_7, ppc1),
                (phone1, ppc1, constants.MESSAGE_1, ppc1),
                (phone2, ppc1, constants.MESSAGE_7, ppc1),
                (phone1, ppc1, constants.MESSAGE_1, ppc1),
                (phone2, ppc1, constants.MESSAGE_7, ppc1),
            ],
            # Try to change registration from a different phone
            [
                (phone1, ppc1, constants.MESSAGE_1, ppc1),
                (phone2, ppc2, constants.MESSAGE_2, ppc1),  # sorry charlie
                # then from the original phone
                (phone1, ppc2, constants.MESSAGE_1, ppc2),  # that's ok - change 1
                # again from another phone
                (phone2, ppc3, constants.MESSAGE_2, ppc2),
                # back to original phone
                (phone1, ppc3, constants.MESSAGE_4, ppc3),  # change 2 - 1 left
                # try other phone again
                (phone2, ppc4, constants.MESSAGE_2, ppc3),
                # original phone again
                (phone1, ppc2, constants.MESSAGE_5, ppc2),  # 3rd change is the last
                (phone1, ppc4, constants.MESSAGE_6, ppc2),  # too many, sorry
                (phone1, ppc5, constants.MESSAGE_6, ppc2),  # still too many
                # Once you've used up your changes, even sending your current
                # registration results in message 6
                (phone1, ppc2, constants.MESSAGE_6, ppc2),
            ],
            # After changing the registration, the repeat count is reset
            [
                (phone1, ppc1, constants.MESSAGE_1, ppc1),
                (phone1, ppc1, constants.MESSAGE_1, ppc1),  # 2nd time - msg 1
                (phone1, ppc1, constants.MESSAGE_1, ppc1),  # 3rd time - msg 1 (enhanced)
                (phone1, ppc2, constants.MESSAGE_1, ppc2),   # change #1 reg - reset counter
                (phone1, ppc2, constants.MESSAGE_1, ppc2),  # 2nd time, same data as #1 change
                (phone1, ppc2, constants.MESSAGE_1, ppc2),  # 3rd time, same data as #1 change
                (phone1, ppc3, constants.MESSAGE_4, ppc3),   # change reg - reset counter
                (phone1, ppc2, constants.MESSAGE_5, ppc2),  # final change
                (phone1, ppc2, constants.MESSAGE_6, ppc2),   # no more changes, always 6
            ],
        ]

        for one_test in test_data:
            # Reset state
            Registration.objects.unfiltered().delete()
            for from_phone, center_id, expected_response, expected_center_id in one_test:
                text = "%s*%s" % (nid1, center_id)
                conn = self.lookup_connections(identities=[from_phone])[0]
                self.receive(text, conn, fields=self.fields)

                # Check the response
                self.assertEqual(expected_response, self.get_last_response_code())
                # Check the state
                reg = Registration.objects.get(citizen__national_id=nid1)
                self.assertEqual(int(expected_center_id), reg.registration_center.center_id)

    def test_input_triggers_proper_response(self):
        short_center_id = '%s*%s' % (
            self.good_nid, get_random_number_string(length=constants.CENTER_ID_LENGTH - 1))
        long_center_id = '%s*%s' % (
            self.good_nid, get_random_number_string(length=constants.CENTER_ID_LENGTH + 1))
        short_nid = "%s*%s" % (
            get_random_number_string(length=constants.NID_LENGTH - 1), self.good_center_id)
        long_nid = "%s*%s" % (
            get_random_number_string(length=constants.NID_LENGTH + 1), self.good_center_id)
        three_ids = "%s*%s*123" % (self.good_nid, self.good_center_id)
        io_table = [
            ("garbage", constants.MESSAGE_INCORRECT),
            (get_random_number_string(), constants.VOTER_QUERY_NID_WRONG_LENGTH),
            (short_center_id, constants.RESPONSE_CENTER_ID_WRONG_LENGTH),
            (long_center_id, constants.RESPONSE_CENTER_ID_WRONG_LENGTH),
            (short_nid, constants.RESPONSE_NID_WRONG_LENGTH),
            (long_nid, constants.RESPONSE_NID_WRONG_LENGTH),
            (three_ids, constants.MESSAGE_INCORRECT),
        ]
        # send the messages
        for (input, _) in io_table:
            self.receive(input, self.conn, fields=self.fields)
        # strip out our split messages
        outputs = [o.fields['message_code'] for o in self.outbound if not o.fields.get('split')]
        for (i, (_, expected_output)) in enumerate(io_table):
            self.assertEqual(outputs[i], expected_output)

    def test_unexpected_error(self):
        with patch.object(PatternHandler, 'dispatch') as dispatch:
            dispatch.side_effect = ValueError
            self.receive("Anything", self.conn, fields=self.fields)
        self.assertEqual(self.outbound[0].fields['message_code'],
                         constants.RESPONSE_SERVER_ERROR)

    @patch('register.handlers.process_registration_request', autospec=True)
    def test_valid_nid(self, mock_prr):
        center_name = "A Random Center"
        person_name = "A Random Name"
        msg = "%s*%s" % (self.good_nid, self.good_center_id)
        mock_prr.return_value = Result('', constants.RESPONSE_VALID_REGISTRATION,
                                       dict(person=person_name,
                                            centre=center_name,
                                            code=int(self.good_center_id)))
        self.receive(msg, self.conn, fields=self.fields)
        self.assertEqual(self.outbound[0].fields['message_code'],
                         constants.RESPONSE_VALID_REGISTRATION)
        # message was saved
        sms = SMS.objects.get(message=msg)
        self.assertEqual(SMS.REGISTRATION, sms.msg_type)
        # response was saved
        sms = SMS.objects.filter(to_number=self.conn.identity)
        self.assertNotEqual(sms.count(), 0)

    @patch('register.processors.process_registration_request', autospec=True)
    def test_invalid_center_id(self, mock_prr):
        msg = "%s*%s" % (self.good_nid, self.good_center_id)
        mock_prr.return_value = Result('', constants.RESPONSE_CENTER_ID_INVALID)
        self.receive(msg, self.conn, fields=self.fields)
        self.assertEqual(self.get_last_response_code(), constants.RESPONSE_CENTER_ID_INVALID)

    @patch('register.handlers.registration_allowed')
    def test_outside_registration_period(self, mock_is_open):
        mock_is_open.return_value = False
        RegistrationCenterFactory(center_id=self.good_center_id)
        msg = "%s*%s" % (self.good_nid, self.good_center_id)
        self.receive(msg, self.conn, fields=self.fields)
        self.assertEqual(self.get_last_response_code(), constants.REGISTRATION_NOT_OPEN)

    def test_not_started(self):
        self.reg_period.start_time = FUTURE_DAY
        self.reg_period.save()
        RegistrationCenterFactory(center_id=self.good_center_id)
        msg = "%s*%s" % (self.good_nid, self.good_center_id)
        self.receive(msg, self.conn, fields=self.fields)
        self.assertEqual(self.get_last_response_code(), constants.REGISTRATION_NOT_OPEN)

    def test_has_ended(self):
        self.reg_period.end_time = PAST_DAY
        self.reg_period.save()
        self.election.polling_end_time = PAST_DAY
        self.election.save()
        RegistrationCenterFactory(center_id=self.good_center_id)
        msg = "%s*%s" % (self.good_nid, self.good_center_id)
        self.receive(msg, self.conn, fields=self.fields)
        self.assertEqual(self.get_last_response_code(), constants.REGISTRATION_NOT_OPEN)

    def test_we_only_handle_our_shortcode(self):
        msg = "garbage"
        not_our_shortcode = '11111'
        self.receive(msg, self.conn, fields={'to_addr': not_our_shortcode})
        # We do send a default response, but we test that more below.
        self.assertEqual(1, len(self.full_outbound()))

    def test_that_we_save_incoming_sms_when_closed(self):
        self.reg_period.start_time = FUTURE_DAY
        self.reg_period.save()
        self.election.polling_start_time = FUTURE_DAY
        self.election.save()
        msg = "garbage"
        for shortcode in set((settings.REGISTRATION_SHORT_CODE,
                              settings.VOTER_QUERY_SHORT_CODE, settings.REPORTS_SHORT_CODE)):
            self.receive(msg, self.conn, fields={'to_addr': shortcode})
            # test that we save the incoming SMS
            incoming = SMS.objects.filter(to_number=shortcode)
            self.assertEqual(len(incoming), 1)


@patch('register.handlers.process_registration_lookup')
class QueryDuringRegistration(LibyaRapidTest):
    """
    Voter query should work any time.
    """

    def setUp(self):
        self.conn = self.lookup_connections(identities='111')[0]
        self.good_nid = get_random_number_string(length=constants.NID_LENGTH)
        self.fields = {'to_addr': settings.REGISTRATION_SHORT_CODE}
        self.msg = "%s" % (self.good_nid)
        self.election = ElectionFactory(polling_start_time=PAST_DAY, polling_end_time=FUTURE_DAY)

    def test_query_before_reg_opens(self, mock_lookup):
        RegistrationPeriodFactory(start_time=FUTURE_DAY, end_time=FUTURE_DAY)
        self.receive(self.msg, self.conn, fields=self.fields)
        self.assertTrue(mock_lookup.called)

    def test_query_during_reg(self, mock_lookup):
        RegistrationPeriodFactory(start_time=PAST_DAY, end_time=FUTURE_DAY)
        mock_lookup.return_value = Result('1', constants.VOTER_QUERY_NOT_FOUND)
        self.receive(self.msg, self.conn, fields=self.fields)
        self.assertTrue(mock_lookup.called)

    def test_query_after_reg_closes(self, mock_lookup):
        # after reg closes but before polling is over
        self.election.polling_start_time = FUTURE_DAY
        self.election.save()
        RegistrationPeriodFactory(start_time=PAST_DAY, end_time=PAST_DAY)
        mock_lookup.return_value = Result('1', constants.VOTER_QUERY_NOT_FOUND)
        self.receive(self.msg, self.conn, fields=self.fields)
        self.assertTrue(mock_lookup.called)

    def test_query_after_polling(self, mock_lookup):
        # after polling is over, voters can still check their registrations
        RegistrationPeriodFactory(start_time=PAST_DAY, end_time=PAST_DAY)
        self.election.polling_end_time = PAST_DAY
        self.election.save()
        self.receive(self.msg, self.conn, fields=self.fields)
        self.assertTrue(mock_lookup.called)


class PreprocessAppTest(LibyaRapidTest):

    def setUp(self):
        self.conn = self.lookup_connections(identities='111')[0]
        self.fields = {'to_addr': settings.REGISTRATION_SHORT_CODE}

    def test_incoming_message_phone_numbers(self):
        self.receive("garbage", self.conn, fields=self.fields)
        sms = SMS.objects.filter(from_number=self.conn.identity)[0]
        self.assertNotEqual(sms.from_number, '')
        self.assertNotEqual(sms.to_number, '')

    def test_outgoing_message_phone_numbers(self):
        self.send("garbage", self.conn)
        sms = SMS.objects.filter(to_number=self.conn.identity)[0]
        self.assertNotEqual(sms.from_number, '')
        self.assertNotEqual(sms.to_number, '')

    def test_outgoing_response_has_same_msg_type(self):
        self.receive("garbage", self.conn, fields=self.fields)
        incoming_msg_type = SMS.objects.get(from_number=self.conn.identity).msg_type
        # could be multiple outgoing msgs, if split
        outgoing_msgs = SMS.objects.filter(to_number=self.conn.identity)
        for outgoing_msg in outgoing_msgs:
            self.assertEqual(incoming_msg_type, outgoing_msg.msg_type)

    def test_outgoing_message_code_is_copied_to_incoming_sms(self):
        self.receive("garbage", self.conn, fields=self.fields)
        incoming_msg = SMS.objects.get(from_number=self.conn.identity)
        outgoing_msg = SMS.objects.get(to_number=self.conn.identity)
        self.assertEqual(incoming_msg.message_code, outgoing_msg.message_code)
        self.assertNotEqual(incoming_msg.message_code, 0)

    def test_nonreply_outgoing_have_zero_message_code(self):
        self.send("garbage", self.conn, fields=self.fields)
        outgoing_msg = SMS.objects.get(to_number=self.conn.identity)
        self.assertEqual(outgoing_msg.message_code, 0)

    def test_replies_have_link_to_incoming_sms(self):
        self.receive("garbage", self.conn, fields=self.fields)
        incoming_msg = SMS.objects.get(from_number=self.conn.identity)
        outgoing_msg = SMS.objects.get(to_number=self.conn.identity)
        self.assertEqual(outgoing_msg.in_response_to, incoming_msg)

    def test_nonreplies_dont_have_link_to_incoming_sms(self):
        self.send("garbage", self.conn, fields=self.fields)
        outgoing_msg = SMS.objects.get(to_number=self.conn.identity)
        self.assertEqual(outgoing_msg.in_response_to, None)

    def test_outgoing_nonreplies_have_default_from_number(self):
        # By default, nonreplies should have from_number=REGISTRATION_SHORT_CODE
        self.send("garbage", self.conn, fields=self.fields)
        outgoing_msg = SMS.objects.get(to_number=self.conn.identity)
        self.assertEqual(outgoing_msg.from_number, settings.REGISTRATION_SHORT_CODE)

    def test_outgoing_nonreplies_have_customizable_from_number(self):
        # from_number can be customized by setting msg.fields['endpoint']
        self.fields['endpoint'] = 'my-shortcode'
        self.send("garbage", self.conn, fields=self.fields)
        outgoing_msg = SMS.objects.get(to_number=self.conn.identity)
        self.assertEqual(outgoing_msg.from_number, 'my-shortcode')

    def test_msg_to_mult_connections_creates_mult_sms(self):
        conn1 = self.create_connection()
        conn2 = self.create_connection()
        self.send('garbage', [conn1, conn2])
        sms_msgs = SMS.objects.filter(direction=OUTGOING)
        self.assertEqual(sms_msgs.count(), 2)

    @override_settings(SPLIT_LONG_MESSAGES=False)
    def test_91_char_message_is_not_split(self):
        ascii_text = 'garbage'
        arabic_text = 'قمامة'
        long_text = ('%s %s' % (ascii_text, arabic_text)) * 7
        assert 91 == len(long_text)
        self.send(long_text, self.conn)
        # test that only 1 message gets sent (no splitting)
        self.assertEqual(len(self.sent_messages), 1)
        # test that our paginator is not in the message
        self.assertEqual(self.sent_messages[0]['text'], long_text)
        sms_entries = SMS.objects.filter(to_number=self.conn.identity)
        # test only 1 SMS entry is created
        self.assertEqual(sms_entries.count(), 1)

    @override_settings(SPLIT_LONG_MESSAGES=True)
    def test_91_char_message_is_split_into_two(self):
        ascii_text = 'garbage'
        arabic_text = 'قمامة'
        long_text = ('%s %s' % (ascii_text, arabic_text)) * 7
        assert 91 == len(long_text)
        self.send(long_text, self.conn)
        # test that there are 2 messages sent
        self.assertEqual(len(self.sent_messages), 2)
        # test that our paginator is in the message
        self.assertIn('[1/2]', self.sent_messages[0]['text'])
        self.assertIn('[2/2]', self.sent_messages[1]['text'])
        sms_entries = SMS.objects.filter(to_number=self.conn.identity)
        # test that 2 and only 2 SMS entries are created
        self.assertEqual(sms_entries.count(), 2)
        # test that entries have order fields
        for sms in sms_entries:
            self.assertIn(sms.order, [1, 2])

    @override_settings(SPLIT_LONG_MESSAGES=True)
    def test_that_message_is_split_on_word_boundaries(self):
        long_text = ('We the people of the United States, in order to form a more perfect '
                     'union, establish justice, insure domestic tranquility, provide for '
                     'the common defense, promote the general welfare, and secure the '
                     'blessings of liberty to ourselves and our posterity, do ordain '
                     'and establish this Constitution for the United States of America.')
        self.send(long_text, self.conn)
        output_table = ['[1/6] We the people of the United States, in order to form a more',
                        '[2/6] perfect union, establish justice, insure domestic tranquility,',
                        '[3/6] provide for the common defense, promote the general welfare,',
                        '[4/6] and secure the blessings of liberty to ourselves and our',
                        '[5/6] posterity, do ordain and establish this Constitution for the',
                        '[6/6] United States of America.']
        for i, expected in enumerate(output_table):
            self.assertEqual(self.sent_messages[i]['text'], output_table[i])


class BlacklistTest(LibyaRapidTest):

    def setUp(self):
        self.fields = {'to_addr': settings.REGISTRATION_SHORT_CODE}
        RegistrationPeriodFactory(start_time=PAST_DAY, end_time=FUTURE_DAY)

    @patch.object(handlers.DefaultHandler, 'handle')
    def test_blacklisted_number_gets_rejected(self, default_handler):
        # create a blacklisted number
        blacklisted_number = '218923456789'
        self.fields['from_addr'] = blacklisted_number
        BlacklistFactory(phone_number=blacklisted_number)
        blacklisted_conn = self.create_connection(data={'identity': blacklisted_number})
        # receive a message from that number
        self.receive('garbage', blacklisted_conn, fields=self.fields)
        # make sure message is rejected and DefaultHandler isn't called
        self.assertEqual(self.get_last_response_code(), constants.BLACKLISTED_NUMBER)
        self.assertFalse(default_handler.called)

    @patch.object(handlers.DefaultHandler, 'handle')
    def test_deleted_blacklisted_number_gets_accepted(self, default_handler):
        # create an un-blacklisted number
        un_blacklisted_number = '218923456789'
        self.fields['from_addr'] = un_blacklisted_number
        BlacklistFactory(phone_number=un_blacklisted_number, deleted=True)
        blacklisted_conn = self.create_connection(data={'identity': un_blacklisted_number})
        # receive a message from that number
        self.receive('garbage', blacklisted_conn, fields=self.fields)
        # make sure DefaultHandler is called
        self.assertTrue(default_handler.called)


class VoterQueryInputOutputTest(LibyaRapidTest):
    def setUp(self):
        self.bad_nid = get_random_number_string(length=constants.NID_LENGTH + 1)
        self.conn = self.create_connection()
        self.fields = {'to_addr': settings.VOTER_QUERY_SHORT_CODE}
        self.garbage = "PING"
        self.good_nid = get_random_number_string(length=constants.NID_LENGTH)
        self.good_center_id = get_random_number_string(length=constants.CENTER_ID_LENGTH)

    @patch.object(utils, "tool_1_enabled")
    @patch("register.handlers.process_registration_lookup")
    def test_registration_open(self, processor, tool_1_enabled):
        # Can query during registration
        tool_1_enabled.return_value = True
        result = Mock(message="success", message_code=constants.VOTER_QUERY_REGISTERED_AT)
        processor.return_value = result
        io_table = [
            (self.garbage, constants.MESSAGE_INCORRECT),
            (str(self.bad_nid), constants.VOTER_QUERY_NID_WRONG_LENGTH),
            (str(self.good_nid), constants.VOTER_QUERY_REGISTERED_AT),
        ]
        for incoming_message, expected_code in io_table:
            self.receive(incoming_message, self.conn, fields=self.fields)
            self.assertEqual(self.get_last_response_code(), expected_code)

    @patch("register.handlers.process_registration_lookup")
    def test_between_registration_and_election(self, processor):
        # Can query between registration and election
        RegistrationPeriodFactory(start_time=PAST_DAY, end_time=PAST_DAY)
        ElectionFactory(polling_start_time=FUTURE_DAY, polling_end_time=FUTURE_DAY)
        io_table = [
            (self.garbage, constants.REGISTRATION_NOT_OPEN),
            (str(self.bad_nid), constants.VOTER_QUERY_NID_WRONG_LENGTH),
            (str(self.good_nid), constants.VOTER_QUERY_REGISTERED_AT),
        ]
        result = Mock(message="success", message_code=constants.VOTER_QUERY_REGISTERED_AT)
        processor.return_value = result
        for incoming_message, expected_code in io_table:
            self.receive(incoming_message, self.conn, fields=self.fields)
            self.assertEqual(self.get_last_response_code(), expected_code)

    @patch("register.handlers.process_registration_lookup")
    def test_after_election(self, processor):
        # can still query registration after election
        RegistrationPeriodFactory(start_time=PAST_DAY, end_time=PAST_DAY)
        ElectionFactory(polling_start_time=PAST_DAY, polling_end_time=PAST_DAY)
        io_table = [
            (self.garbage, constants.REGISTRATION_NOT_OPEN),
            (str(self.bad_nid), constants.VOTER_QUERY_NID_WRONG_LENGTH),
            (str(self.good_nid), constants.VOTER_QUERY_REGISTERED_AT),
        ]
        result = Mock(message="success", message_code=constants.VOTER_QUERY_REGISTERED_AT)
        processor.return_value = result
        for incoming_message, expected_code in io_table:
            self.receive(incoming_message, self.conn, fields=self.fields)
            self.assertEqual(self.get_last_response_code(), expected_code)


class VoterQueryBlacklistTest(LibyaRapidTest):

    def setUp(self):
        self.fields = {'to_addr': settings.VOTER_QUERY_SHORT_CODE}

    @patch.object(handlers.DefaultHandler, 'handle')
    def test_blacklisted_number_gets_rejected(self, default_handler):
        # create a blacklisted number
        blacklisted_number = '218923456789'
        self.fields['from_addr'] = blacklisted_number
        BlacklistFactory(phone_number=blacklisted_number)
        blacklisted_conn = self.create_connection(data={'identity': blacklisted_number})
        # receive a message from that number
        self.receive('garbage', blacklisted_conn, fields=self.fields)
        # make sure message is rejected and DefaultHandler isn't called
        self.assertEqual(self.get_last_response_code(), constants.BLACKLISTED_NUMBER)
        self.assertFalse(default_handler.called)


class DefaultHandlerTest(LibyaRapidTest):
    def test_default_handler(self):
        # If we receive a message that's addressed to some number
        # we don't recognize, we should still save the incoming
        # message and send some response.
        from_addr = '111'
        to_addr = '98765'  # NOT one of our numbers
        fields = {
            'to_addr': to_addr,
            'from_addr': from_addr,
        }
        conn = self.lookup_connections(identities=[from_addr])[0]
        self.receive('garbage', conn, fields=fields)
        # The incoming message should have been saved
        sms = SMS.objects.get(direction=INCOMING)
        self.assertEqual(from_addr, sms.from_number)
        self.assertEqual(to_addr, sms.to_number)
        self.assertEqual(SMS.NOT_HANDLED, sms.msg_type)
        # And an outgoing message should have been sent
        out = SMS.objects.get(to_number=from_addr, direction=OUTGOING)
        self.assertEqual(from_addr, out.to_number)
        self.assertEqual(to_addr, out.from_number)
        self.assertEqual(SMS.NOT_HANDLED, out.msg_type)
        self.assertIn('was not understood', out.message)
        outbound_messages = self.full_outbound()
        # we should only have sent one
        self.assertEqual(1, len(outbound_messages))
