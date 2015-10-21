# -*- coding: utf-8 -*-

# Python imports
from __future__ import unicode_literals
from __future__ import division
import logging

# Django imports
from django.test import TestCase
from django.conf import settings

# Project imports
from .factories import create_voters
from ..models import Station, station_distributor
from ..utils import format_name
from libya_elections.constants import MALE, FEMALE, UNISEX
from register.tests.factories import RegistrationCenterFactory


# Silence the logging output.
logger = logging.getLogger('rollgen')
logger.handlers = []
logger.addHandler(logging.NullHandler())


class TestStation(TestCase):
    """Exercise the Station model (mostly testing property behavior)"""

    def test_unicode(self):
        """Test that unicode() behaves well before saving.

        The unicode() method has to work even when no attrs are set.
        """
        station = Station()
        # This must merely not blow up.
        unicode(station)

    def test_attrs_pre_roll(self):
        """Exercise some attrs before the roll is set"""
        station = Station()
        self.assertEqual(station.roll, [])
        self.assertIsNone(station.number)
        self.assertIsNone(station.gender)
        self.assertIsNone(station.n_registrants)
        self.assertIsNone(station.first_voter_number)
        self.assertIsNone(station.last_voter_number)
        self.assertEqual(station.first_voter_name, '')
        self.assertEqual(station.last_voter_name, '')

    def test_attrs_post_roll(self):
        """Exercise some attrs after the roll is set"""
        center = RegistrationCenterFactory()
        roll = create_voters(4, gender=MALE, center=center)

        station = station_distributor(roll)[0]

        self.assertEqual(station.roll, roll)

        # number and gender are set by station_distributor() so they're unchanged here.
        self.assertEqual(station.number, 1)
        self.assertEqual(station.gender, MALE)
        self.assertEqual(station.n_registrants, len(roll))
        self.assertEqual(station.first_voter_number, 1)
        self.assertEqual(station.last_voter_number, len(roll))
        self.assertEqual(station.first_voter_name, format_name(roll[0]))
        self.assertEqual(station.last_voter_name, format_name(roll[-1]))


def stations_to_dicts(stations):
    """Utility function to dict-ify the station attrs set by station_distributor()"""
    return [{'number': station.number, 'gender': station.gender, 'roll': station.roll} for
            station in stations]


class TestStationDistributor(TestCase):
    """Exercise models.station_distributor() (the factory function for Stations).

    station_distributor() contains a lengthy comment that describes 9 categories of male/female
    voter division that it can encounter. The tests called test_unisex_case_N() refer to the
    cases documented in that comment.
    """
    def test_simple(self):
        """test simple case with one male and one female station"""
        # Simple case: 1 station each of males & females.
        voter_roll = create_voters((settings.ROLLGEN_UNISEX_TRIGGER + 1) * 2)

        males = [voter for voter in voter_roll if voter.gender == MALE]
        females = [voter for voter in voter_roll if voter.gender == FEMALE]

        expected_stations = [dict(number=1, gender=MALE, roll=males),
                             dict(number=2, gender=FEMALE, roll=females)]

        actual_stations = stations_to_dicts(station_distributor(voter_roll))

        self.assertListEqual(expected_stations, actual_stations)

    def test_registrants_per_station_max(self):
        """Test that settings.ROLLGEN_REGISTRANTS_PER_STATION_MAX is respected"""
        # Create a station with exactly ROLLGEN_REGISTRANTS_PER_STATION_MAX voters and ensure that
        # they are not split across two stations. I create enough other voters to avoid getting
        # tangled up in the unisex code.
        n_voters = settings.ROLLGEN_REGISTRANTS_PER_STATION_MAX + settings.ROLLGEN_UNISEX_TRIGGER

        voter_roll = create_voters(n_voters, MALE)
        # Make a small contingent female
        for voter in voter_roll[:settings.ROLLGEN_UNISEX_TRIGGER]:
            voter.gender = FEMALE

        males = voter_roll[settings.ROLLGEN_UNISEX_TRIGGER:]
        females = voter_roll[:settings.ROLLGEN_UNISEX_TRIGGER]

        expected_stations = [dict(number=1, gender=MALE, roll=males),
                             dict(number=2, gender=FEMALE, roll=females)]

        actual_stations = stations_to_dicts(station_distributor(voter_roll))

        self.assertListEqual(expected_stations, actual_stations)

        # Create a station with exactly ROLLGEN_REGISTRANTS_PER_STATION_MAX + 1 voters and ensure
        # that they are split across two stations.
        n_voters = settings.ROLLGEN_REGISTRANTS_PER_STATION_MAX + 1 + \
            settings.ROLLGEN_UNISEX_TRIGGER

        voter_roll = create_voters(n_voters, MALE)
        # Make a small contingent female
        for voter in voter_roll[:settings.ROLLGEN_UNISEX_TRIGGER]:
            voter.gender = FEMALE

        males = voter_roll[settings.ROLLGEN_UNISEX_TRIGGER:]
        # Males are split evenly into 2 stations.
        males1 = males[:settings.ROLLGEN_REGISTRANTS_PER_STATION_MAX // 2]
        males2 = males[settings.ROLLGEN_REGISTRANTS_PER_STATION_MAX // 2:]
        females = voter_roll[:settings.ROLLGEN_UNISEX_TRIGGER]

        expected_stations = [dict(number=1, gender=MALE, roll=males1),
                             dict(number=2, gender=MALE, roll=males2),
                             dict(number=3, gender=FEMALE, roll=females)]

        actual_stations = stations_to_dicts(station_distributor(voter_roll))

        self.assertListEqual(expected_stations, actual_stations)

    def test_unisex_case_1(self):
        """test case 1 (no voters of either gender)
        1. n_males registered == 0         AND n_females registered == 0
        """
        expected_stations = []

        actual_stations = station_distributor([])

        self.assertListEqual(expected_stations, actual_stations)

    def test_unisex_case_2(self):
        """test case 2 (no males, few females)
        2. n_males registered == 0         AND n_females registered > 0 and < 25
        """
        voter_roll = create_voters(settings.ROLLGEN_UNISEX_TRIGGER - 1, FEMALE)

        expected_stations = [dict(number=1, gender=FEMALE, roll=voter_roll)]

        actual_stations = stations_to_dicts(station_distributor(voter_roll))

        self.assertListEqual(expected_stations, actual_stations)

    def test_unisex_case_3(self):
        """test case 3 (no males, lots of females)
        3. n_males registered == 0         AND n_females registered >= 25
        """
        voter_roll = create_voters(settings.ROLLGEN_UNISEX_TRIGGER, FEMALE)

        expected_stations = [dict(number=1, gender=FEMALE, roll=voter_roll)]

        actual_stations = stations_to_dicts(station_distributor(voter_roll))

        self.assertListEqual(expected_stations, actual_stations)

    def test_unisex_case_4(self):
        """test case 4 (no males, lots of females)
        4. n_males registered > 0 and < 25 AND n_females registered == 0
        """
        voter_roll = create_voters(settings.ROLLGEN_UNISEX_TRIGGER - 1, MALE)

        expected_stations = [dict(number=1, gender=MALE, roll=voter_roll)]

        actual_stations = stations_to_dicts(station_distributor(voter_roll))

        self.assertListEqual(expected_stations, actual_stations)

    def test_unisex_case_5(self):
        """test case 5 (few males, few females)
        5. n_males registered > 0 and < 25 AND n_females registered > 0 and < 25
        """
        voter_roll = create_voters((settings.ROLLGEN_UNISEX_TRIGGER * 2) - 2)

        males = [voter for voter in voter_roll if voter.gender == MALE]
        females = [voter for voter in voter_roll if voter.gender == FEMALE]

        expected_stations = [dict(number=1, gender=UNISEX, roll=males + females)]

        actual_stations = stations_to_dicts(station_distributor(voter_roll))

        self.assertListEqual(expected_stations, actual_stations)

    def test_unisex_case_6(self):
        """test case 6 (few males, lots of females)
        6. n_males registered > 0 and < 25 AND n_females registered >= 25
        """
        n_voters = settings.ROLLGEN_UNISEX_TRIGGER - 1 + settings.ROLLGEN_UNISEX_TRIGGER
        voter_roll = create_voters(n_voters, MALE)

        for voter in voter_roll[settings.ROLLGEN_UNISEX_TRIGGER - 1:]:
            voter.gender = FEMALE

        males = [voter for voter in voter_roll if voter.gender == MALE]
        females = [voter for voter in voter_roll if voter.gender == FEMALE]

        expected_stations = [dict(number=1, gender=UNISEX, roll=males + females)]

        actual_stations = stations_to_dicts(station_distributor(voter_roll))

        self.assertListEqual(expected_stations, actual_stations)

    def test_unisex_case_7(self):
        """test case 7 (lots of males, no females)
        7. n_males registered >= 25        AND n_females registered == 0
        """
        voter_roll = create_voters(settings.ROLLGEN_UNISEX_TRIGGER + 1, MALE)

        expected_stations = [dict(number=1, gender=MALE, roll=voter_roll)]

        actual_stations = stations_to_dicts(station_distributor(voter_roll))

        self.assertListEqual(expected_stations, actual_stations)

    def test_unisex_case_8(self):
        """test case 8 (lots of males, few females)
        8. n_males registered >= 25        AND n_females registered > 0 and < 25
        """
        voter_roll = create_voters((settings.ROLLGEN_UNISEX_TRIGGER + 2), MALE)

        voter_roll[-1].gender = FEMALE

        males = [voter for voter in voter_roll if voter.gender == MALE]
        females = [voter for voter in voter_roll if voter.gender == FEMALE]

        expected_stations = [dict(number=1, gender=UNISEX, roll=males + females)]

        actual_stations = stations_to_dicts(station_distributor(voter_roll))

        self.assertListEqual(expected_stations, actual_stations)

    def test_unisex_case_9(self):
        """test case 9 (lots of males, lots of females)
        9. n_males registered >= 25        AND n_females registered >= 25
        """
        voter_roll = create_voters((settings.ROLLGEN_UNISEX_TRIGGER * 2) + 2)

        males = [voter for voter in voter_roll if voter.gender == MALE]
        females = [voter for voter in voter_roll if voter.gender == FEMALE]

        expected_stations = [dict(number=1, gender=MALE, roll=males),
                             dict(number=2, gender=FEMALE, roll=females)]

        actual_stations = stations_to_dicts(station_distributor(voter_roll))

        self.assertListEqual(expected_stations, actual_stations)

    def test_even_distribution(self):
        """Test that a station big enough for two is split relatively evenly."""
        n_voters = settings.ROLLGEN_REGISTRANTS_PER_STATION_MAX + 10

        voter_roll = create_voters(n_voters, MALE)

        males1 = voter_roll[:n_voters // 2]
        males2 = voter_roll[n_voters // 2:]

        expected_stations = [dict(number=1, gender=MALE, roll=males1),
                             dict(number=2, gender=MALE, roll=males2)]

        actual_stations = stations_to_dicts(station_distributor(voter_roll))

        self.assertListEqual(expected_stations, actual_stations)

    def test_registrants_per_station_max_with_unisex(self):
        """Test that code creating a too-large unisex station behaves according to issue 98.

        Technically, we're not supposed to create a station > ROLLGEN_REGISTRANTS_PER_STATION_MAX,
        but unisex stations are complicated so they get an exception to the rule.

        See https://github.com/hnec-vr/roll-generator/issues/98
        """
        n_females = settings.ROLLGEN_REGISTRANTS_PER_STATION_MAX - 1
        n_males = settings.ROLLGEN_UNISEX_TRIGGER - 1
        n_voters = n_females + n_males
        voter_roll = create_voters(n_voters, FEMALE)

        for voter in voter_roll[:n_males]:
            voter.gender = MALE

        # Ideally this would be two stations, in reality there's only one.
        expected_stations = [dict(number=1, gender=UNISEX, roll=voter_roll), ]

        actual_stations = stations_to_dicts(station_distributor(voter_roll))

        self.assertListEqual(expected_stations, actual_stations)
