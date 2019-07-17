from django.conf import settings

from civil_registry.tests.factories import CitizenFactory
from libya_elections import constants
from libya_elections.utils import get_random_number_string
from register.tests.base import LibyaRapidTest
from register.tests.factories import RegistrationFactory


class VoterQueryEndToEndTest(LibyaRapidTest):
    def setUp(self):
        self.conn = self.create_connection()
        self.fields = {'to_addr': settings.VOTER_QUERY_SHORT_CODE}
        self.bad_nid = get_random_number_string(length=constants.NID_LENGTH)
        self.bad_length_nid = get_random_number_string(length=constants.NID_LENGTH + 1)
        self.nid_without_person = get_random_number_string(length=constants.NID_LENGTH)
        self.garbage = "PING"
        self.citizen = CitizenFactory()
        self.good_nid = str(self.citizen.national_id)

    def test_nlid_does_not_exist(self):
        # NID doesn't exist, return VOTER_QUERY_NOT_FOUND
        self.receive(self.bad_nid, self.conn, fields=self.fields)
        self.assertEqual(self.get_last_response_code(), constants.VOTER_QUERY_NOT_FOUND)

    def test_citizen_is_not_registered(self):
        # national_id received has no registration associated with it
        self.receive(self.good_nid, self.conn, fields=self.fields)
        self.assertEqual(self.get_last_response_code(), constants.VOTER_QUERY_NOT_REGISTERED)

    def test_citizen_has_no_confirmed_registrations(self):
        # national id received has one unconfirmed registration
        RegistrationFactory(citizen=self.citizen)  # unconfirmed registration
        self.receive(self.good_nid, self.conn, fields=self.fields)
        self.assertEqual(self.get_last_response_code(), constants.VOTER_QUERY_NOT_REGISTERED)

    def test_citizen_has_multiple_unconfirmed_registrations(self):
        # national id has multiple unconfirmed registration associated with it
        RegistrationFactory(citizen=self.citizen)  # unconfirmed registration
        RegistrationFactory(citizen=self.citizen)  # unconfirmed registration
        self.receive(self.good_nid, self.conn, fields=self.fields)
        self.assertEqual(self.get_last_response_code(), constants.VOTER_QUERY_NOT_REGISTERED)

    def test_citizen_is_registered(self):
        # national id belongs to a citizen in our db and has one confirmed registration
        RegistrationFactory(citizen=self.citizen, archive_time=None)
        self.receive(self.good_nid, self.conn, fields=self.fields)
        self.assertEqual(self.get_last_response_code(), constants.VOTER_QUERY_REGISTERED_AT)

    def test_nid_wrong_length(self):
        # nid received is not 12 digits long
        self.receive(self.bad_length_nid, self.conn, fields=self.fields)
        self.assertEqual(self.get_last_response_code(), constants.VOTER_QUERY_NID_WRONG_LENGTH)

    def test_garbage_message_during_query_period(self):
        # message received does not match any of our patterns.
        self.receive(self.garbage, self.conn, fields=self.fields)
        self.assertEqual(self.get_last_response_code(), constants.REGISTRATION_NOT_OPEN)
