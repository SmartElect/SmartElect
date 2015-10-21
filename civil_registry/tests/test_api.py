"""
Tests for voter_api
"""
import base64
from datetime import datetime
from httplib import OK, NOT_FOUND
import json
from django.conf import settings
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.utils.timezone import now
from civil_registry.models import CitizenMetadata
from civil_registry.tests.factories import CitizenFactory
from libya_elections.constants import FEMALE


class VoterGetTest(TestCase):
    def setUp(self):
        credentials = base64.b64encode(settings.VOTER_API_USER + ':' + settings.VOTER_API_PASSWORD)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Basic ' + credentials

    def test_get_voter(self):
        birth_datetime = datetime(1902, 3, 2)
        citizen = CitizenFactory(
            birth_date=birth_datetime.date(),
            gender=FEMALE,
        )

        url = reverse('get-voter', kwargs=dict(voter_id=citizen.national_id))
        rsp = self.client.get(url)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        result = json.loads(rsp.content.decode('utf-8'))
        self.assertEqual(citizen.national_id, result['national_id'])
        self.assertEqual(citizen.fbr_number, result['registry_number'])
        self.assertEqual(citizen.civil_registry_id, result['person_id'])
        self.assertEqual(birth_datetime.isoformat(), result['birth_date'])
        self.assertEqual('F', result['gender'])

        # Parse the date the same way we've been doing in nlid/api.py:
        date = datetime.strptime(result['birth_date'][:10], '%Y-%m-%d').date()
        self.assertEqual(birth_datetime.date(), date)

    def test_get_nonexistent_voter(self):
        url = reverse('get-voter', kwargs=dict(voter_id=123456789012))
        rsp = self.client.get(url)
        self.assertEqual(NOT_FOUND, rsp.status_code, msg=rsp.content.decode('utf-8'))

    def test_get_metadata(self):
        url = reverse('get-metadata')
        rsp = self.client.get(url)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        result = json.loads(rsp.content.decode('utf-8'))
        self.assertEqual(0, result['num_rows'])
        self.assertNotIn('dump_date', result)

        citizen = CitizenFactory()
        rsp = self.client.get(url)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        result = json.loads(rsp.content.decode('utf-8'))
        self.assertEqual(1, result['num_rows'])
        self.assertEqual(citizen.national_id, result['max_id'])
        self.assertEqual(citizen.national_id, result['min_id'])
        self.assertNotIn('dump_date', result)

        timestamp = now()
        CitizenMetadata.objects.create(dump_time=timestamp)
        rsp = self.client.get(url)
        self.assertEqual(OK, rsp.status_code, msg=rsp.content.decode('utf-8'))
        result = json.loads(rsp.content.decode('utf-8'))
        self.assertEqual(timestamp.isoformat(), result['dump_date'])
