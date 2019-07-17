# Python imports
import os
import random

# 3rd party imports
import factory

# project imports
from ..constants import CITIZEN_SORT_FIELDS
from civil_registry.models import Citizen
from civil_registry.tests.factories import CitizenFactory
from libya_elections.constants import MALE, FEMALE
from register.tests.factories import RegistrationFactory, SMSFactory

filename = os.path.join(os.path.dirname(__file__), '_random_arabic_person_names.txt')
with open(filename, 'rb') as f:
    words = f.read().decode('utf-8')
# Remove blank lines and extraneous whitespace.
person_names = [word.strip() for word in words.split('\n') if word.strip()]

filename = os.path.join(os.path.dirname(__file__), '_random_arabic_place_names.txt')
with open(filename, 'rb') as f:
    words = f.read().decode('utf-8')
# Remove blank lines and extraneous whitespace.
place_names = [word.strip() for word in words.split('\n') if word.strip()]


def generate_arabic_place_name(min_length=0):
    """Return a randomly generated, potentially multi-word fake Arabic place name"""
    make_name = lambda n_words: ' '.join(random.sample(place_names, n_words))

    n_words = 3
    name = make_name(n_words)
    while len(name) < min_length:
        n_words += 1
        name = make_name(n_words)

    return name


def create_voters(n_voters, gender=None, center=None):
    """Create voters in bulk, with options not available via the factory"""
    toggle_gender = not bool(gender)
    if not gender:
        gender = MALE

    # I create a dummy SMS here for optimization. If the VoterFactory creates a registration for
    # each user and I don't pass an SMS instance, it will create an SMS for each registration which
    # triggers the creation of a Citizen and a Backend. Passing a dummy SMS reduces this overhead
    # from O(3 * n_voters) to O(1). It's logically incorrect to associate the same SMS with multiple
    # registrations, but rollgen doesn't pay attention to SMSes.
    sms = SMSFactory()

    voter_ids = []
    for i in range(n_voters):
        if toggle_gender:
            gender = FEMALE if (gender == MALE) else MALE
        voter = VoterFactory(gender=gender, post__center=center, post__sms=sms)
        voter_ids.append(voter.pk)

    # It's a bit painful performance-wise, but in order to sort these the same way as
    # get_voter_roll(), I have to let the database do the sorting.
    return list(Citizen.objects.filter(pk__in=voter_ids).order_by(*CITIZEN_SORT_FIELDS))


class VoterFactory(CitizenFactory):
    """Create a voter with a random Arabic name"""
    @factory.post_generation
    def post(instance, create, extracted, **kwargs):
        instance.first_name = random.choice(person_names)
        instance.father_name = random.choice(person_names)
        instance.grandfather_name = random.choice(person_names)
        instance.family_name = random.choice(person_names)
        instance.mother_name = random.choice(person_names)

        if kwargs['center']:
            # Register this voter to this center
            reg_kwargs = dict(citizen=instance, registration_center=kwargs['center'],
                              archive_time=None)
            if 'sms' in kwargs and kwargs['sms']:
                reg_kwargs['sms'] = kwargs['sms']
            RegistrationFactory(**reg_kwargs)
