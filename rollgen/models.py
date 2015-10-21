from __future__ import unicode_literals
from __future__ import division

from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from .utils import format_name, even_chunker
from libya_elections.abstract import AbstractTimestampModel
from libya_elections.libya_bread import ElectionFormatterMixin, RegistrationCenterFormatterMixin
from libya_elections.constants import MALE, FEMALE, UNISEX
from register.models import RegistrationCenter
from voting.models import Election


def station_distributor(roll):
    """Given a list of Citizens (voters at a center), evenly distribute them into stations by
    gender.

    Return a list of unsaved Station instances. Each station has the gender and number attributes
    populated. Station numbers start at 1 and are unique within the center.

    This is the factory function for Station instances. You should get all of your Stations from
    here rather than calling the Station ctor directly (test code excepted of course).

    The registrants (Citizens) in roll have a new field 'registrant_number' that's unique
    within the center. It also starts counting at 1.

    This function usually creates a unisex station if either gender has less than UNISEX_TRIGGER
    voters. See complex rules in inline comments. In unisex centers, men are listed first.
    """
    # group by gender
    grouped = {FEMALE: [], MALE: []}
    for voter in roll:
        grouped[voter.gender].append(voter)

    # stations contains 2 lists, each list contains Station instances
    stations = {FEMALE: [], MALE: []}
    # Counter for registrant number. Each registrant in a center gets a unique number; they do
    # *not* repeat across male/female/unisex stations.
    registrant_number = 1

    # chunk into stations
    for gender in (MALE, FEMALE):
        num_reg = len(grouped[gender])
        num_chunks = ((num_reg - 1) // settings.ROLLGEN_REGISTRANTS_PER_STATION_MAX) + 1
        # 550 -> 1, 551 -> 2

        for chunk in even_chunker(grouped[gender], num_chunks):
            station_roll = chunk
            for voter in station_roll:
                voter.registrant_number = registrant_number
                registrant_number += 1

            station = Station(gender=gender)
            station.roll = station_roll
            stations[gender].append(station)

    # Below a certain threshold of registrants at a station, we want to combine the last male &
    # female stations into a single unisex station. This sounds simple, but there's a lot of cases
    # to consider. Fortunately, the code above does a nice job distributing registrants and will not
    # create underused stations unless it has no other choice. (e.g. If there are 560 male
    # registrants, it creates two stations of 280 registrants each rather than one with 550 and
    # another with 10. Similarly, if there are only 40 male registrants, it smart enough to leave
    # them in one station rather than splitting them into two stations of 20 each.)
    #
    # You can see how it's chunking with this code:
    #   print('  males: ' + ','.join([str(len(station['roll'])) for station in stations[MALE]]))
    #   print('females: ' + ','.join([str(len(station['roll'])) for station in stations[FEMALE]]))
    #
    # Given the above, there are 9 cases to consider --
    #
    #    1. n_males registered == 0         AND n_females registered == 0
    #    2. n_males registered == 0         AND n_females registered > 0 and < 25
    #    3. n_males registered == 0         AND n_females registered >= 25
    #    4. n_males registered > 0 and < 25 AND n_females registered == 0
    #    5. n_males registered > 0 and < 25 AND n_females registered > 0 and < 25
    #    6. n_males registered > 0 and < 25 AND n_females registered >= 25
    #    7. n_males registered >= 25        AND n_females registered == 0
    #    8. n_males registered >= 25        AND n_females registered > 0 and < 25
    #    9. n_males registered >= 25        AND n_females registered >= 25
    #
    # Fortunately, in the first case we can't create a unisex station (no voters at all, which I'm
    # not even sure this code will ever see), and in any case where there are no voters of a given
    # gender (cases 1, 2, 3, 4, and 7), then creating a unisex station doesn't consolidate stations
    # anyway, so there's no point to doing it.
    # Case 9 is the "normal" case that doesn't require creation of a unisex station.
    # Therefore, only cases 5, 6, and 8 require a unisex station.

    # Note that the requirements document Polling Planning Rules eng 20140526 0900.docx says,
    # "There may not be more than one uni-sex station per centre."
    unisex_station = None

    if (not stations[MALE]) or (not stations[FEMALE]):
        # Cases 1, 2, 3, 4, and 7 from above ==> nothing to do.
        pass
    else:
        n_males = len(grouped[MALE])
        n_females = len(grouped[FEMALE])

        if (n_males < settings.ROLLGEN_UNISEX_TRIGGER) or \
           (n_females < settings.ROLLGEN_UNISEX_TRIGGER):
            # Cases 5, 6, and 8 from above. One or both of these is too small and will have to be
            # combined with the other to create a unisex station.
            # There's a potential small bug here where the two stations being combined may create
            # a unisex station that has > REGISTRANTS_PER_STATION_MAX voters. We've decided to let
            # it slide on the grounds that (a) it's not likely to happen, (b) the consequences are
            # small if it does happen, and (c) it's difficult to fix.
            # ref: https://github.com/hnec-vr/roll-generator/issues/98
            if n_females < settings.ROLLGEN_UNISEX_TRIGGER:
                # This handles both cases 5 and 8.
                big_gender = MALE
                little_gender = FEMALE
            else:
                # Case 6.
                big_gender = FEMALE
                little_gender = MALE

            roll_men = stations[MALE][-1].roll
            roll_women = stations[FEMALE][-1].roll
            unisex_station = stations[big_gender].pop(-1)
            unisex_station.gender = UNISEX
            # In the roll of a unisex station, "Men will always be listed first."
            # ref: Polling Planning Rules eng 20140118 2020
            unisex_station.roll = roll_men + roll_women
            stations[little_gender] = []
        # else:
            # Case 9 ==> nothing to do.

    stations = stations[MALE] + stations[FEMALE]

    if unisex_station:
        stations.append(unisex_station)

    # Assign a unique number to each station. Station numbers do *not* duplicate between
    # male/female/unisex stations.
    for station_number, station in enumerate(stations):
        station.number = station_number + 1

    return stations


class Station(ElectionFormatterMixin, RegistrationCenterFormatterMixin, AbstractTimestampModel):
    """A voting station. These should only be created through station_distributor().

    Each station has a roll attribute that's not stored in the database. The roll is a list of
    people assigned to vote at that station. Populating the roll attribute triggers populating
    other attributes, specifically: n_registrants, first_voter_name, first_voter_number,
    last_voter_name, and last_voter_number.

    The only attributes that users of this class should populate are election, center, number,
    gender, and roll. (The other attributes would be read-only properties if Django models allowed
    such a thing.) And in practice, number, gender and roll are populated by the
    function station_distributor() (q.v.).
    """
    election = models.ForeignKey(Election, verbose_name=_('election'))
    center = models.ForeignKey(RegistrationCenter, verbose_name=_('registration center'))
    number = models.PositiveSmallIntegerField(_('number'))
    gender = models.PositiveSmallIntegerField(_('gender'))
    n_registrants = models.IntegerField(_('number of registrants'))
    first_voter_name = models.CharField(_('first voter name'), max_length=255)
    first_voter_number = models.IntegerField(_('first voter number'))
    last_voter_name = models.CharField(_('last voter name'), max_length=255)
    last_voter_number = models.IntegerField(_('last voter number'))

    # Voter roll is accessed through a property and is not stored in the database.
    _roll = []

    @property
    def roll(self):
        return self._roll

    @roll.setter
    def roll(self, voter_roll):
        """Sets voter roll. See class docstring for details."""
        self._roll = voter_roll
        self.n_registrants = len(voter_roll)
        self.first_voter_name = format_name(self.first_voter)
        self.first_voter_number = self.first_voter.registrant_number
        self.last_voter_name = format_name(self.last_voter)
        self.last_voter_number = self.last_voter.registrant_number

    @property
    def first_voter(self):
        return self._roll[0] if self._roll else None

    @property
    def last_voter(self):
        return self._roll[-1] if self._roll else None

    class Meta:
        verbose_name = _("station")
        verbose_name_plural = _("stations")
        ordering = ('center__center_id', 'number', )
        unique_together = ('election', 'center', 'number', )
        permissions = [
            ("browse_station", "Can list stations"),
            ("read_station", "Can read a station"),
        ]

    def __unicode__(self):
        # While debugging, it's possible that the center might not yet be set when this is invoked.
        center_id = self.center.center_id if self.center_id else "[None]"
        return "Center {}, Station {}".format(center_id, self.number)
