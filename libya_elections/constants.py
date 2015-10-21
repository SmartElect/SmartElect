# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _

"""
NB: See docs/sms_responses.rst for IMPORTANT INFORMATION about how
to add new messages or change existing messages.
"""

# Message directions
INCOMING = 1
OUTGOING = 2

MALE = 1
FEMALE = 2
# Only rollgen uses UNISEX.
UNISEX = 3

GENDER_CHOICES = (
    (FEMALE, _('Female')),
    (MALE, _('Male')),
    (UNISEX, _('Unisex')),
)

GENDER_MAP = {k: v for k, v in GENDER_CHOICES}
GENDER_ABBRS = {FEMALE: 'f', MALE: 'm', UNISEX: 'u'}

# length of IDs
NID_LENGTH = 12
CENTER_ID_LENGTH = 5
CENTER_ID_MIN_INT_VALUE = 10 ** (CENTER_ID_LENGTH - 1)
CENTER_ID_MAX_INT_VALUE = 10 ** (CENTER_ID_LENGTH) - 1
FORM_ID_LENGTH_MIN = 6
FORM_ID_LENGTH_MAX = 8

# Subcon 998 is a special, virtual subcon associated with split centers.
SPLIT_CENTER_SUBCONSTITUENCY_ID = 998
# Dummy Value for centers with no (NamedThing)
NO_NAMEDTHING = 999

# Used in polling reports
CENTER_OPEN_INDICATOR = 0
FIRST_PERIOD_NUMBER = 1
LAST_PERIOD_NUMBER = 4
PRELIMINARY_VOTE_COUNT_INDICATOR = 5

# Standard Libya date format is D/M/Y. Ref: http://en.wikipedia.org/wiki/Date_format_by_country
LIBYA_DATE_FORMAT = '%d/%m/%Y'
LIBYA_DATETIME_FORMAT = LIBYA_DATE_FORMAT + ' %H:%M'

# Template constants

# For FK links from Bread Read views:
ANCHOR_SNIPPET = '<a href="{}">{}</a>'

PHONE_NUMBER_MSG = _("Please enter a valid phone number (218xxxxxxxxx or 88216xxxxxxxx) "
                     "without punctuation or spaces.")

# SMS responses - do NOT change these values
# Also, do NOT re-use numbers. Always create new messages
# using new numbers (higher than the current highest number).
# The numbers are visible to users and used in documentation.
MESSAGE_1 = 1
MESSAGE_2 = 3
MESSAGE_4 = 4
MESSAGE_5 = 5
MESSAGE_6 = 6
MESSAGE_7 = MESSAGE_2
RESPONSE_VALID_REGISTRATION = MESSAGE_1
RESPONSE_CENTER_ID_INVALID = 8
RESPONSE_NID_INVALID = 9
RESPONSE_NID_WRONG_LENGTH = 10
RESPONSE_CENTER_ID_WRONG_LENGTH = 11
RESPONSE_ONE_NUMBER = 12
RESPONSE_SERVER_ERROR = 13
MESSAGE_INCORRECT = 14
REGISTRATION_NOT_OPEN = 31
VOTER_QUERY_INVALID_FORMAT = 40
VOTER_QUERY_NOT_FOUND = 41
VOTER_QUERY_NOT_REGISTERED = 42
VOTER_QUERY_PROBLEM_ENCOUNTERED = 43
VOTER_QUERY_REGISTERED_AT = 44
VOTER_QUERY_NID_WRONG_LENGTH = 45
FBRN_MISMATCH = 49
BLACKLISTED_NUMBER = 50
NOT_WHITELISTED_NUMBER = 51
CENTER_NOT_ACCEPTING_REGISTRATIONS = 52
REMINDER_CHECKIN = 54
REMINDER_REPORT = 55
REMINDER_LAST_REPORT = 56
REMINDER_CLOSE = 57
# More registration messages
TOO_MANY_REGISTRATIONS_ON_PHONE = 71
AT_MAXIMUM_REGISTRATIONS_ON_PHONE = 72
ONE_MORE_REGISTRATION_ON_PHONE = 73
# Polling report and new generic messages
POLLING_NOT_OPEN = 74
POLLING_REPORT_INVALID = 75
PHONE_NOT_ACTIVATED = 76
PHONE_ACTIVATED = 77
INVALID_CENTER_ID = 78
POLLING_REPORT_PHONE_UNAUTHORIZED = 79
POLLING_REPORT_RECEIVED = 81
POLLING_REPORT_CENTER_MISMATCH = 82
SERVER_ERROR = 83
NID_INVALID = 84
CENTER_OPENING_NOT_AUTHORIZED = 85
CENTER_OPENED = 86
PRELIMINARY_VOTES_REPORT = 87
POLLING_REPORT_RECEIVED_VERY_HIGH_TURNOUT = 88
POLLING_REPORT_RECEIVED_NO_REGISTRANTS = 89
# We don't know what to do with your message
PUNT = 90

# Arabic digits
EASTERN_ARABIC_DIGITS = '٠١٢٣٤٥٦٧٨٩'
# U+060C is the preferred comma for Libyan Arabic.
ARABIC_COMMA = '\u060C'
