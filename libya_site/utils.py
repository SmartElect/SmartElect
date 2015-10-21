import random
import string

from django.conf import settings
from django.utils.formats import number_format

from libya_elections import constants


def random_alphanumeric_string(
        size=8,
        chars=string.ascii_uppercase + string.digits +
        string.ascii_lowercase):
    return ''.join(random.choice(chars) for __ in range(size))


def random_digit_challenge():
    """
    Return a tuple of (challenge, valid-response) for django-simple-captcha.
    """
    num_string = random_alphanumeric_string(size=settings.CAPTCHA_LENGTH,
                                            chars='0123456789')
    return num_string, num_string


def create_arabic_trans_table():
    """
    Return a mapping of Eastern Arabic Unicode ordinals to Western Arabic Unicode ordinals,
    which can be used by the unicode-string.translate() function.
    """
    eastern = [ord(char) for char in constants.EASTERN_ARABIC_DIGITS]
    western = unicode(string.digits)
    return dict(zip(eastern, western))


def intcomma(value):
    """
    Return a human-readable integer in the same format as the humanize.intcomma template tag.
    """
    return number_format(value, force_grouping=True)


def intcomma_if(d, k):
    """ Return human-readable integer of value d[k] if k is in dictionary d.
    Otherwise, return an empty string.
    """
    if k in d:
        return intcomma(d[k])
    else:
        return ''
