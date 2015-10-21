# -*- coding: utf-8 -*-
# Python imports
import base64
from decimal import Decimal, InvalidOperation
import functools
from httplib import UNAUTHORIZED
import logging
import random
import re
import string

# Django imports
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.auth.views import redirect_to_login
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.fields import FieldDoesNotExist
from django.http import HttpResponseBadRequest, HttpResponse
from django.template.defaultfilters import yesno, capfirst
from django.utils.functional import lazy
from django.utils.translation import get_language, ugettext as _
from django.utils.timezone import now
from django.views.decorators.debug import sensitive_variables

# 3rd party imports
from braces.views import PermissionRequiredMixin, MultiplePermissionsRequiredMixin
from pytz import utc

# This project's imports
from .constants import ARABIC_COMMA

BAD_REQUEST = HttpResponseBadRequest.status_code


logger = logging.getLogger(__name__)


def ensure_unique(model, instance, fieldname, **kwargs):
    # Ensure there are no other instances with the same value of
    # fieldname among undeleted records of this model
    #
    # :param kwargs: additional query params when checking for dupes
    if not instance.deleted:
        query_parms = {
            'deleted': False,
            fieldname: getattr(instance, fieldname),
        }
        query_parms.update(**kwargs)
        others = model.objects.filter(**query_parms)
        if instance.pk:
            others = others.exclude(pk=instance.pk)
        if others.exists():
            verbose_name = model._meta.get_field(fieldname).verbose_name
            msg = _("Duplicate value for {fieldname}").format(fieldname=verbose_name)
            raise ValidationError(msg)


def get_permission_object_by_name(name,
                                  permission_class=None,
                                  contenttype_class=None,
                                  create_if_needed=False):
    """Given a Django permission name like `app_label.change_thing`,
    return its Permission object.

    You can pass in the Permission class when using this from a migration.

    Pass in create_if_needed=True to have the permission created if it doesn't exist.
    """
    # I hate Django permissions
    app_label, codename = name.split(".", 1)
    if not permission_class:
        permission_class = Permission
    # Is that enough to be unique? Hope so
    try:
        return permission_class.objects.get(content_type__app_label=app_label,
                                            codename=codename)
    except permission_class.DoesNotExist:
        if create_if_needed:
            if not contenttype_class:
                contenttype_class = ContentType
            perm_name, model_name = codename.split("_", 1)
            ct, unused = contenttype_class.objects.get_or_create(app_label=app_label,
                                                                 model=model_name)
            # Come up with a permission name. E.g. if code name is 'add_user',
            # the full name might be 'Can add user'
            full_name = "Can %s %s" % (perm_name, model_name)
            return permission_class.objects.create(content_type=ct, codename=codename,
                                                   name=full_name)
        print("NO SUCH PERMISSION: %s, %s" % (app_label, codename))
        raise


def permission_names_to_objects(names):
    """
    Given an iterable of permission names (e.g. 'app_label.add_model'),
    return an iterable of Permission objects for them.
    """
    return [get_permission_object_by_name(name) for name in names]


def astz(dt, tz):
    """
    Given a datetime object and a timezone object, return a new
    datetime object that represents the same moment, but written
    in terms of the new timezone.
    :param dt: a datetime object
    :param tz: a timezone object
    :return: a datetime object
    """
    # See http://pythonhosted.org/pytz/ for why this is
    # not as trivial as it might first appear.
    return tz.normalize(dt.astimezone(tz))


def max_non_none_datetime(*values):
    """
    Given some datetime objects, and ignoring any None values,
    return the datetime object that occurs latest in
    absolute time, or None.
    """
    # Start by annotating the non-none values with the
    # corresponding UTC times
    annotated_list = [(astz(value, utc), value) for value in values if value is not None]
    if not annotated_list:
        return None
    # Now find the max tuple, which will be the one with the max UTC. The
    # second item in the tuple will be the corresponding original object.
    unused, max_object = max(annotated_list)
    return max_object


def min_non_none_datetime(*values):
    """
    Given some datetime objects, and ignoring any None values,
    return the datetime object that occurs earliest in
    absolute time, or None.
    """
    # Start by annotating the non-none values with the
    # corresponding UTC times
    annotated_list = [(astz(value, utc), value) for value in values if value is not None]
    if not annotated_list:
        return None
    # Now find the min tuple, which will be the one with the min UTC. The
    # second item in the tuple will be the corresponding original object.
    unused, min_object = min(annotated_list)
    return min_object


class FormErrorReturns400Mixin(object):
    def form_invalid(self, form):
        # If the form is not valid, return the usual page but with a 400 status
        return self.render_to_response(self.get_context_data(form=form), status=BAD_REQUEST)


NUM_LATLONG_DECIMAL_PLACES = 8
LATLONG_QUANTIZE_PLACES = Decimal(10) ** -NUM_LATLONG_DECIMAL_PLACES
MAX_LATLONG = Decimal('180.0')


def parse_latlong(value):
    """
    Given a string with a decimal value, or a float,
    parse to a Decimal and truncate to the number of places
    we're keeping for lat/long values. Return the result.
    """
    val = Decimal(value).quantize(LATLONG_QUANTIZE_PLACES)
    if val > MAX_LATLONG:
        raise InvalidOperation("Lat or long too large")
    return val


def cleanup_lat_or_long(latlng):
    """
    Given character string that is supposed to contain a latitude or longitude,
    return either a valid Decimal value, or None.

    Note: This assumes E/N and does not handle anything west of Greenwich or
    south of the equator!  If the input has a - or W or S in it, it'll probably
    just fail to recognize it as a valid coordinate and return None.
    """

    # Strip whitespace and degree signs
    s = latlng.strip().rstrip(u'E\xb0')

    # If nothing left, we have no data.
    if len(s) == 0:
        return None

    d = None

    if d is None:
        # See if it's a simple decimal value
        if '.' in s:
            try:
                d = parse_latlong(s)
            except InvalidOperation:
                pass

    if d is None:
        # 290250
        # 204650
        # Assume DDMMSS
        m = re.match(r'^(\d\d)(\d\d)(\d\d)$', s)
        if m:
            val = float(m.group(1)) + float(m.group(2)) / 60.0 + float(m.group(3)) / 3600.0
            d = parse_latlong(val)

    if d is None:
        # 12°37'49.30"
        # 20° 6'9.54"E
        # 20°29'33.84"E
        # 10ْ .05 30 63
        # 12° 2'54.62"
        # 12°37'7.00"
        # Assume the format is:  degrees  minutes  seconds.milliseconds
        m = re.match('r^(\d\d?)\D+(\d\d?)\D+(\d\d?)\D+(\d\d?)$', s)
        if m:
            parts = m.groups()
            val = (float(parts[0])
                   + float(parts[1]) / 60.0
                   + float('%s.%s' % (parts[2], parts[3])) / 3600.0)
            d = parse_latlong(val)

    if d is None:
        # Pick out the groups of digits
        parts = _extract_numerals(s)

        if len(parts) == 4:
            # 12°37'49.30"
            # 20° 6'9.54"E
            # 20°29'33.84"E
            # 10ْ .05 30 63
            # 12° 2'54.62"
            # 12°37'7.00"
            # Assume the format is:  degrees  minutes  seconds.fractionalseconds
            val = (float(parts[0])
                   + float(parts[1]) / 60.0
                   + float('%s.%s' % (parts[2], parts[3])) / 3600.0)
            d = parse_latlong(val)

        elif len(parts) == 3:
            # 12ْ 14 23
            # 14ْ 25 816
            # 57 " .579" .12
            # 32ْ 453 700
            # Hmm - assume degrees minutes seconds?
            if float(parts[1]) > 60.0 or float(parts[2]) > 60.0:
                # Just makes no sense - ignore it
                return None
            val = (float(parts[0])
                   + float(parts[1]) / 60.0
                   + float(parts[2]) / 3600.0)
            d = parse_latlong(val)

        elif len(parts) == 2:
            # 12° 2
            d = parse_latlong(float(parts[0]) + float(parts[1]) / 60.0)

    if d is None:
        return None

    if d > Decimal('180.0'):
        return None

    return d


NONDIGITS_RE = re.compile('[^\d]', flags=re.UNICODE)


@sensitive_variables()
def clean_input_msg(msg_text):
    """Process a user's message, finding all number-strings, translating
    them to American strings, and then joining them with an asterisk. We do not
    validate them. That will be done by the handlers.
    """
    return u'*'.join(str(long(num)) for num in _extract_numerals(msg_text))


def _extract_numerals(msg_text):
    """Return a list of all strings of numerals. Works on american and
    eastern arabic numerals (Python FTW!)
    """
    # split string using any non-digits as a delimiter, then drop the empty strings
    number_list = [n for n in NONDIGITS_RE.split(msg_text) if n]
    return number_list


def get_now():
    # make sure this is timezone-aware
    return now()


class LoginPermissionRequiredMixin(PermissionRequiredMixin):
    """Combines LoginRequiredMixin and PermissionRequiredMixin, according to our rules.

    When an unauthenticated user visits a page that requires login, s/he gets redirected to the
    login page.
    When an authenticated user lacks the permission for a page, s/he gets a 403.

    In contrast to the LoginRequiredMixin and PermissionRequiredMixin, the subclass need not
    set the raise_exception attribute. (It's ignored.)
    """
    def dispatch(self, request, *args, **kwargs):
        # User has to be logged in
        if not request.user.is_authenticated():
            return redirect_to_login(request.get_full_path(),
                                     self.get_login_url(),
                                     self.get_redirect_field_name())

        # Force raise_exception to be True when invoking PermissionRequiredMixin.
        self.raise_exception = True
        return super(LoginPermissionRequiredMixin, self).dispatch(request, *args, **kwargs)


class LoginMultiplePermissionsRequiredMixin(MultiplePermissionsRequiredMixin):
    """Combines LoginRequiredMixin and MultiplePermissionsRequiredMixin, according to our rules.

    When an unauthenticated user visits a page that requires login, s/he gets redirected to the
    login page.
    When an authenticated user lacks the permission for a page, s/he gets a 403.

    In contrast to the LoginRequiredMixin and PermissionRequiredMixin, the subclass need not
    set the raise_exception attribute. (It's ignored.)

    Also provides the non-standard pre_dispatch_check which runs before invoking
    the parent dispatch method, and if it returns a response, will
    return that instead of calling parent dispatch.
    """
    def pre_dispatch_check(self, request, *args, **kwargs):
        return None

    def dispatch(self, request, *args, **kwargs):
        # User has to be logged in
        if not request.user.is_authenticated():
            return redirect_to_login(request.get_full_path(),
                                     self.get_login_url(),
                                     self.get_redirect_field_name())
        # Now we know they're logged in.
        response = self.pre_dispatch_check(request, *args, **kwargs)
        if response:
            return response

        # Force raise_exception to be True when invoking LoginMultiplePermissionsRequiredMixin.
        self.raise_exception = True
        return super(LoginMultiplePermissionsRequiredMixin, self).dispatch(request, *args, **kwargs)


def get_db_connection_tz(cursor):
    """ Return time zone of the Django database connection with which
    the specified cursor is associated.
    """
    cursor.execute("SHOW timezone;")
    return cursor.fetchall()[0][0]  # e.g., [(u'UTC',)][0][0]


class ConnectionInTZ(object):
    """ This context manager manipulates the time zone of the Django database
    connection with which the specified cursor is associated, ensuring that
    the original time zone is restored at the end of the context.

    Example use:

       with ConnectionInTZ(cursor, 'Libya'):
           cursor.execute(something)
           cursor.fetchall()

    Django throws an exception when handling some SQL time-related constructs
    in local time; DATE_TRUNC('day', <field>) can't be used, for example.
    """

    def __init__(self, cursor, desired_tz):
        self.cursor = cursor
        self.tz = desired_tz

    def __enter__(self):
        self.saved_tz = get_db_connection_tz(self.cursor)
        self.cursor.execute("SET timezone=%s;", [self.tz])

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.cursor.execute("SET timezone=%s;", [self.saved_tz])


def refresh_model(obj):
    """
    Given an instance of a model, fetch a fresh copy from the database and return it.
    """
    return type(obj).objects.get(pk=obj.pk)


def random_string(length=255, extra_chars=''):
    """ Generate a random string of characters.

    :param length: Length of generated string.
    :param extra_chars: Additional characters to include in generated
        string.
    """
    chars = string.letters + extra_chars
    return ''.join([random.choice(chars) for i in range(length)])


def get_random_number_string(length=10, choices=string.digits, no_leading_zero=True):
    first = random.choice(choices)
    # if no_leading_zero, then force first number to be nonzero
    while no_leading_zero and not int(first):
        # keep picking until we get nonzero
        first = random.choice(choices)
    return first + u''.join(random.choice(choices) for __ in xrange(length - 1))


def shuffle_string(s):
    """Randomly shuffle a string and return result."""
    l = list(s)
    random.shuffle(l)
    return u''.join(l)


def strip_nondigits(string):
    """
    Return a string containing only the digits of the input string.
    """
    return ''.join([c for c in string if c.isdigit()])


def at_noon(dt):
    """
    Given a datetime, return a new datetime at noon on the
    same day.
    """
    return dt.replace(hour=12, minute=0, second=0, microsecond=0)


def at_midnight(dt):
    """
    Given a datetime, return a new datetime at midnight on the
    same day.
    """
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def find_overlapping_records(start_time, end_time, queryset, start_field, end_field):
    """
    A utility to determine if any records in a queryset overlap with the period
    passed in as start_time -> end_time

    Returns a queryset with the overlapping records.

    :param start_time: the start of the period to look for overlaps of
    :param end_time: the end of the period to look for overlaps of
    :param queryset: the records to look for an overlap in
    :param start_field: name of the field in the model in the queryset that has
    the start time for the record
    :param end_field: name of the field in the model in the queryset that has
    the end time for the record
    :return: a queryset with the overlapping records. (could be empty)
    """

    # Check for overlaps.  Here are the cases we need to catch -
    #
    # An existing overlapping period might:
    # * start during this period,
    # * or end during this period,
    # * or completely encompass this period.

    # (The case of an existing period that starts and ends inside
    # the new period will be caught by both of the first two checks,
    # so we don't need to test it separately.)

    # Also recall that a period runs from exactly its start time,
    # up to but not including its end time.

    # First case: Check for an existing period starting during this period.
    # That would mean:
    #   the record in the database's start_time >= this records start time
    # and
    #   < this record's end time.
    # (It's okay for it to start exactly at this record's end time,
    # because then they don't overlap.)
    #
    # existing:           S              E
    #                     v
    # self:       s            e
    # query_start_during = Q(start_time__gte=start_time, start_time__lt=end_time)
    query_start_during = Q(
        **{
            '%s__gte' % start_field: start_time,
            '%s__lt' % start_field: end_time,
        }
    )

    # Second case: Check for an existing period that ends during this period.
    # That would mean:
    #   the database's end_time > this record's start time
    # and
    #   <= this record's end time
    #
    # existing:           S               E
    #                                     v
    # self:                      s                e
    # query_end_during = Q(end_time__gt=start_time, end_time__lte=end_time)
    query_end_during = Q(
        **{
            '%s__gt' % end_field: start_time,
            '%s__lte' % end_field: end_time,
        }
    )

    # Third case: Check for an existing period that completely encompasses
    # this period.  That would mean:
    #   the record in the database's start time is less than this record's start time,
    # and
    #   its end time is greater than this records end time.
    #
    # existing:          S                     E
    #                    v                     v
    # self:                    s        e
    # query_encompass = Q(start_time__lte=start_time, end_time__gt=end_time)
    query_encompass = Q(
        **{
            '%s__lte' % start_field: start_time,
            '%s__gt' % end_field: end_time,
        }
    )

    # Any of the ways they can overlap:
    query_overlaps = query_start_during | query_end_during | query_encompass

    # Are there any?
    return queryset.filter(query_overlaps)


def basic_auth_view(auth_db, realm_name):
    """"
    Given an auth dictionary and a realm name,
    returns a new wrapper function that takes a
    view function and returns a wrapped view function.

    This allows decorating a view like so:

    @basic_auth_view(MY_DB_DICT, "secret realm")
    def my_view(request):
        ...

    or

    url(r'...', basic_auth_view(auth_db, realm_name)(ViewClass.as_view()), ...)


    Uses `basic_auth`, see below.
    """

    def basic_auth_view_inner_wrapper(f):
        return basic_auth(f, auth_db, realm_name)

    return basic_auth_view_inner_wrapper


def basic_auth(f, auth_db, realm_name):
    """
    View function wrapper to apply http basic auth.

    Usage:

        def view(request, ...):
            ...
        view = basic_auth(view, auth_db, realm_name)

    or

        url(r'...', basic_auth(ViewClass.as_view(), auth_db, realm_name), ...),

    :param auth_db: Dictionary of user -> password for access to the view.
    :param realm_name: name of the auth realm to return on auth errors.

    Derived (via several steps) from
    https://djangosnippets.org/snippets/243/
    """
    @functools.wraps(f)
    def wrapper(request, *args, **kwargs):
        if 'HTTP_AUTHORIZATION' in request.META:
            auth = request.META['HTTP_AUTHORIZATION'].split()
            if len(auth) == 2 and auth[0].lower() == 'basic':
                username, passwd = base64.b64decode(auth[1]).split(':')
                ok = username in auth_db and passwd == auth_db[username]
                del passwd
                if ok:
                    return f(request, *args, **kwargs)
                logger.error('Bad user id/password %s/******** for view %s' %
                             (username, f.__name__))
                if len(auth_db) == 0:
                    logger.error('User database for this view not set up')
            else:
                logger.error('Unrecognized auth %s for view %s' %
                             (auth, f.__name__))
        response = HttpResponse(status=UNAUTHORIZED)
        response['WWW-Authenticate'] = 'Basic realm="%s"' % realm_name
        return response
    return wrapper


def migrate_permission(apps, schema_editor, perm1, perm2):
    """Gives perm2 to all users and groups that currently have perm1.

    The permissions should be strings in the form "applabel.perm_model", e.g. "voting.read_ballot".

    This is especially useful for migrations.
    """
    User = apps.get_model(settings.AUTH_USER_MODEL)
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    permission_1 = get_permission_object_by_name(perm1, Permission, ContentType, True)
    permission_2 = get_permission_object_by_name(perm2, Permission, ContentType, True)

    for group in Group.objects.filter(permissions=permission_1):
        group.permissions.add(permission_2)
    for user in User.objects.filter(user_permissions=permission_1):
        user.user_permissions.add(permission_2)


def get_comma_delimiter(include_a_space=True):
    """Return the comma delimiter appropriate for the current language (Arabic or English).

    When include_a_space is True (the default), the delimiter includes a space to make the returned
    value easy to use with join() when constructing a list.
    """
    delimiter = ARABIC_COMMA if (get_language() == 'ar') else ','
    if include_a_space:
        delimiter += ' '

    return delimiter


def get_verbose_name(an_object, field_name, init_cap=True):
    """Given a model or model instance, return the verbose_name of the model's field.

    If init_cap is True (the default), the verbose_name will be returned with the first letter
    capitalized which makes the verbose_name look nicer in labels.

    If field_name doesn't refer to a model field, raises a FieldDoesNotExist error.
    """
    # get_field_by_name() can raise FieldDoesNotExist which I simply propogate up to the caller.
    try:
        field = an_object._meta.get_field_by_name(field_name)[0]
    except TypeError:
        # TypeError happens if the caller is very confused and passes an unhashable type such
        # as {} or []. I convert that into a FieldDoesNotExist exception for simplicity.
        raise FieldDoesNotExist("No field named {}".format(str(field_name)))

    verbose_name = field.verbose_name

    if init_cap:
        verbose_name = lazy(capfirst, unicode)(verbose_name)

    return verbose_name


def format_tristate(tristate):
    """Given a boolean or tristate, returns Yes, No, or Maybe as appropriate"""
    return yesno(tristate).capitalize()


def migrate_view_to_read(app_label, model, apps, schema_editor):
    """Migrate view_MODEL to read_MODEL, then delete the view permission object"""
    model = model.lower()
    migrate_permission(apps, schema_editor,
                       # myapp.view_mymodel
                       app_label + ".view_" + model,
                       # myapp.read_mymodel
                       app_label + ".read_" + model)
    # remove view_mymodel
    Permission = apps.get_model('auth', 'Permission')
    Permission.objects.filter(content_type__app_label=app_label,
                              # view_mymodel
                              codename='view_' + model).delete()


def migrate_read_to_view(app_label, model, apps, schema_editor):
    """Migrate read_MODEL to view_MODEL"""
    model = model.lower()
    migrate_permission(apps, schema_editor,
                       # myapp.read_mymodel
                       app_label + ".read_" + model,
                       # myapp.view_mymodel
                       app_label + ".view_" + model)


def add_browse_to_read(app_label, model, apps):
    """Add the new browse_MODEL perm to anyone who has read_MODEL"""
    model = model.lower()
    User = apps.get_model('auth', 'User')
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    # myapp.read_mymodel
    read_name = app_label + '.read_' + model
    # myapp.browse_mymodel
    browse_name = app_label + '.browse_' + model

    perm_read = get_permission_object_by_name(read_name, Permission, ContentType, True)
    perm_browse = get_permission_object_by_name(browse_name, Permission, ContentType, True)

    for group in Group.objects.filter(permissions=perm_read):
        group.permissions.add(perm_browse)

    for user in User.objects.filter(user_permissions=perm_read):
        user.user_permissions.add(perm_browse)


def migrate_bread_permissions_forward(app_label, model_names, apps, schema_editor):
    """For each app/model combo specified, for each user or group that has view permission,
    grant them read permission (creating it if necessary), then delete the view permission
    object. Then add browse to each user or group that has read.
    """
    for model in model_names:
        migrate_view_to_read(app_label, model, apps, schema_editor)
        add_browse_to_read(app_label, model, apps)


def migrate_bread_permissions_backward(app_label, model_names, apps, schema_editor):
    """For each app/model combo specified, give view permission to any user or group that
    has read or browse permission, then remove the read and browse permission objects."""
    for model in model_names:
        read = '%s.read_%s' % (app_label, model)
        view = '%s.view_%s' % (app_label, model)
        browse = '%s.browse_%s' % (app_label, model)
        migrate_permission(apps, schema_editor, read, view)
        migrate_permission(apps, schema_editor, browse, view)
        Permission.objects.filter(content_type__app_label=app_label,
                                  # view_mymodel
                                  codename='read_' + model).delete()
        Permission.objects.filter(content_type__app_label=app_label,
                                  # view_mymodel
                                  codename='browse_' + model).delete()
