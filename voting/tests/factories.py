import random
from datetime import timedelta

from factory import DjangoModelFactory, SubFactory, Sequence
from factory.declarations import LazyAttribute
from factory.fuzzy import FuzzyDateTime

from django.utils.timezone import now

from voting.models import Ballot, Candidate, Election, RegistrationPeriod


start_dt = now()


class ElectionFactory(DjangoModelFactory):
    class Meta:
        model = Election

    name_english = Sequence(lambda n: "Election %d" % n)
    name_arabic = Sequence(lambda n: "Election %d (ar)" % n)

    polling_start_time = FuzzyDateTime(start_dt=start_dt - timedelta(days=2),
                                       end_dt=start_dt - timedelta(days=1))
    polling_end_time = FuzzyDateTime(start_dt=start_dt + timedelta(days=2),
                                     end_dt=start_dt + timedelta(days=3))


class BallotFactory(DjangoModelFactory):
    class Meta:
        model = Ballot

    ballot_type = LazyAttribute(lambda o: random.choice(Ballot.VALID_RACE_TYPES))
    election = SubFactory(ElectionFactory)
    internal_ballot_number = Sequence(int)


class CandidateFactory(DjangoModelFactory):
    class Meta:
        model = Candidate

    ballot = SubFactory(BallotFactory)
    name_english = Sequence(lambda n: "Candidate %d" % n)
    name_arabic = Sequence(lambda n: "Candidate %d (ar)" % n)
    candidate_number = Sequence(int)


class RegistrationPeriodFactory(DjangoModelFactory):
    class Meta:
        model = RegistrationPeriod
