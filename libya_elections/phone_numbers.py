# Python imports
import random

# Django imports
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, MaxLengthValidator
from django.db.models import CharField
from django import forms
from django.utils.html import format_html

# 3rd party imports
from rapidsms.models import Connection
from rapidsms.router import lookup_connections

# This project's imports
from libya_elections.constants import PHONE_NUMBER_MSG
from libya_elections.utils import get_random_number_string, strip_nondigits


# The formats of phone numbers currently valid in Libya:
#   218 + 9 digits  (Libyana, Al Madar)
#   88216 + 8 digits  (Thuraya)

class PhoneNumberValidator(RegexValidator):
    """
    This only accepts phone numbers in canonical format - no whitespace
    or punctuation, just 218xxxxxxxxx or 88216xxxxxxxx.  To clean up
    numbers from human input, call canonicalize_phone_number() on them
    first.
    """
    def __init__(self, regex=None, message=None, code=None, inverse_match=None, flags=None):
        regex = regex or settings.PHONE_NUMBER_REGEX
        message = message or PHONE_NUMBER_MSG
        super(PhoneNumberValidator, self).__init__(regex, message, code, inverse_match, flags)


def is_phone_number_valid(number):
    """
    Return True if PhoneNumberValidator considers the number valid,
    meaning it has to be in canonical form already.
    """
    validator = PhoneNumberValidator()
    try:
        validator(number)
    except ValidationError:
        return False
    else:
        return True


class PhoneNumberFormField(forms.CharField):
    """
    Form field type to use for phone numbers.
    """
    def __init__(self, *args, **kwargs):
        if kwargs.get('disable_help_text'):
            # don't add a message here, hide our arg
            del kwargs['disable_help_text']
        elif not kwargs.get('help_text', False):
            kwargs['help_text'] = PHONE_NUMBER_MSG
        kwargs.setdefault('validators', [])
        kwargs['validators'].append(PhoneNumberValidator())
        kwargs['validators'].append(MaxLengthValidator(settings.MAX_PHONE_NUMBER_LENGTH))
        super(PhoneNumberFormField, self).__init__(*args, **kwargs)

    def clean(self, value):
        value = canonicalize_phone_number(self.to_python(value))
        return super(PhoneNumberFormField, self).clean(value)


class PhoneNumberField(CharField):
    """
    Model field type to use for phone numbers.
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', settings.MAX_PHONE_NUMBER_LENGTH)
        kwargs.setdefault('validators', [])
        kwargs['validators'].append(PhoneNumberValidator())
        super(PhoneNumberField, self).__init__(*args, **kwargs)

    def deconstruct(self):
        """Tweak the way that Django serializes these fields for migrations"""
        name, path, args, kwargs = super(PhoneNumberField, self).deconstruct()
        # Don't encode PhoneNumberValidator into the migrations; we consider it
        # inherent in the PhoneNumberField type
        kwargs['validators'] = [k for k in kwargs['validators']
                                if not isinstance(k, PhoneNumberValidator)]
        # If there are no more validators, don't include validators in the kwargs at all.
        if not kwargs['validators']:
            del kwargs['validators']
        # Note that we do let the 'max_length' value be exposed in the migration, because
        # it comes from the project settings and if that changes, the database will definitely
        # need a schema update.
        return name, path, args, kwargs

    def formfield(self, **kwargs):
        # Use PhoneNumberFormField by default for PhoneNumberField in forms
        defaults = {'form_class': PhoneNumberFormField}
        defaults.update(kwargs)
        return super(PhoneNumberField, self).formfield(**defaults)


def get_random_phone_number():
    """
    Return a valid, random phone number in canonical format.
    """
    return random.choice([
        generate_random_thuraya_number,
        generate_random_almadar_number,
        generate_random_libyana_number
    ])()


def generate_random_thuraya_number():
    return '88216' + get_random_number_string(length=8)


def generate_random_local_libyan_number():
    return random.choice([
        generate_random_almadar_number,
        generate_random_libyana_number
    ])()


def generate_random_almadar_number():
    # 218-91xxxxxxx
    return '21891' + get_random_number_string(length=7)


def generate_random_libyana_number():
    # 218-92xxxxxx
    # 218-94xxxxxx
    return '2189' + random.choice(['2', '4']) + get_random_number_string(length=7)


def format_phone_number(phone):
    """
    Given a phone number as a string of digits (only), format for presentation.
    Local Libya numbers will look like '+218 (0)xx-xxx-xxxx', and Thuraya
    numbers will look like '+88216xxxxxxx' (per Elliott, Hipchat, Dec. 30, 2014).

    You can also use this from a template:

        {% load libya_tags %}
        {{ phone_number|format_phone_number }}
    """
    if phone.startswith('218'):
        return '+' + phone[0:3] + ' (0)' + phone[3:5] + '-' + phone[5:8] + '-' + phone[8:]
    elif phone.startswith('88216'):
        return '+' + phone[0:5] + '-' + phone[5:]
    else:
        return phone  # punt!


def canonicalize_phone_number(phone):
    """
    Given a phone number string that might have been input by a human and
    contain punctuation, spaces, or who knows what, try to
    strip it down to just a string of digits that we can store and compare
    unambiguously.

    Cleans up some human conventions like putting a '0' on the front in
    place of the 218 country code.

    Does not validate that the result is a valid Libyan phone number.

    :param phone: The input
    :return: resulting string of digits
    """

    # How about this format: +218 (0)65-715-0971
    if phone.startswith('+218 (0)'):
        # Convert to 21865-715-0971
        phone = '218' + phone[8:]

    phone = strip_nondigits(phone)

    # Sometimes they enter '218xxxxx' numbers instead as '0xxxxx'.  Usually
    # the first digit of the 'xxxx' part is '9', so assume that.
    if len(phone) == 10 and phone.startswith('09'):
        phone = '218' + phone[1:]

    return phone


# Used from migrations:
def clean_phone_number_database_field(model, fieldname):
    """
    In a migration, check the values of a specific phone number field in a model.
    If they need a little cleaning up, e.g. they look like '09xxxxxxxx'
    and should look like '2189xxxxxxxx', clean them up. Then see if
    the number is valid, and if not, delete the record.

    Usage in migration:

    def some_name(apps, schema_editor):
        FieldStaff = apps.get_model('help_desk', 'fieldstaff')
        clean_phone_number_database_field(FieldStaff, 'phone_number')

    :param model:
    :param fieldname:
    :return:
    """
    validator = PhoneNumberValidator()
    model_name = model._meta.model_name
    for item in model.objects.all():
        number = canonicalize_phone_number(getattr(item, fieldname))
        if number != getattr(item, fieldname):
            setattr(item, fieldname, number)
            item.save()
        try:
            validator(number)
        except ValidationError:
            print("Deleting %s with invalid phone number %s" % (model_name, number))
            item.delete()


def best_connection_for_phone_number(number, backends=None):
    """
    Return a RapidSMS Connection object to use for sending a message
    to the given phone number.

    If we already have Connection objects for the number, use the most
    recently modified one.

    Otherwise, see if we can guess based on looking at the number
    and any backends that have a 'number_regex' defined in settings.

    Fallback to returning a random connection using one of the
    backend names in `backends`, or any of the backends from settings.

    :param number: String containing the phone number in canonical form.
    :param backends: A list of backend names to choose from if we have
    to pick one at random.  Defaults to all backends in settings.
    :return: a rapidsms.models.Connection object
    """

    connection = Connection.objects.filter(identity=number).order_by('-modified_on').first()
    if connection:
        return connection

    for name, backend in settings.INSTALLED_BACKENDS.iteritems():
        if 'number_regex' in backend:
            if backend['number_regex'].match(number):
                return lookup_connections(backend=name, identities=[number])[0]

    # Use any old backend
    backend_names = backends or settings.INSTALLED_BACKENDS.keys()
    backend_name = random.choice(backend_names)
    return lookup_connections(backend_name, identities=[number])[0]


def formatted_phone_number_tag(phone_number):
    """Return a span tag enclosing a formatted phone number.

    When combined with our CSS rules, this span tag will display a phone number
    properly in RTL or LTR directions.

    This is called from FormattedPhoneNumberMixin, but also from other parts of
    the code that don't use FormattedPhoneNumberMixin.
    """
    return format_html('<span class="phone-number">{}</span>', format_phone_number(phone_number))


class FormattedPhoneNumberMixin(object):
    """Adds 2 methods to aid in the formatting of phone numbers to models that
    include this mix-in. This assumes that the model has a field "phone_number"
    that can be handled by format_phone_number().
    """
    def formatted_phone_number(self):
        """Return phone number formatted for display."""
        return format_phone_number(self.phone_number)

    def formatted_phone_number_tag(self):
        """Return formatted_phone_number inside a tag which, when combined with our CSS
        rules, displays a phone number properly in RTL or LTR directions.
        """
        return formatted_phone_number_tag(self.phone_number)
