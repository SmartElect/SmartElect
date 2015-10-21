from civil_registry.models import Citizen
from register.models import SMS

# Ripped from the DB but with some capitalization.
CARRIER_CODING = {2: 'Libyana',
                  3: 'AlMadar',
                  4: 'Thuraya'}

# The code could be refactored further to allow mixed case
# string values as in SMS.DIRECTION_CHOICES.
MESSAGE_DIRECTION = dict([(direction_value, direction_string.lower())
                          for direction_value, direction_string
                          in SMS.DIRECTION_CHOICES])

MESSAGE_TYPES = dict(SMS.MESSAGE_TYPES)

GENDER_CODING = dict(Citizen.GENDERS)

AGE_RANGES = [(18, 29), (30, 39), (40, 49), (50, 59), (60, None)]

AGE_CODING = {}

for (low, high) in AGE_RANGES:
    if high is None:
        key = '{}+'.format(low)
        high = 200
    else:
        key = '{}-{}'.format(low, high)
    for i in range(low, high + 1):
        AGE_CODING[i] = key
