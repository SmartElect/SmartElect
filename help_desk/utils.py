import locale
import logging

from django.contrib.auth.models import Permission, Group
from django.db.models.fields import BLANK_CHOICE_DASH
from django.utils.translation import ugettext_lazy as _

from .models import HELP_DESK_OPERATORS_GROUP, HELP_DESK_VIEW_GROUP, \
    HELP_DESK_SUPERVISORS_GROUP, HELP_DESK_SENIOR_STAFF_GROUP, HELP_DESK_MANAGERS_GROUP, \
    HELP_DESK_GROUP_PERMISSIONS


logger = logging.getLogger(__name__)


def _get_all_perm_names_for_group(group_name):
    """
    Looking at HELP_DESK_GROUP_PERMISSIONS, return a list of all
    the permission names that members of the named group should have.
    The list of permissions for a group in HELP_DESK_GROUP_PERMISSIONS
    can include both permission names and group names.
    """
    perm_names = set()
    for item in HELP_DESK_GROUP_PERMISSIONS[group_name]:
        if '.' in item:
            # permission name
            perm_names.add(item)
        else:
            # group name
            perm_names |= _get_all_perm_names_for_group(item)
    return perm_names


def get_group_choices(user):
    """
    Return the choices list of help desk groups that the given user
    is authorized to grant to other users.
    """
    # include an empty choice, to allow removal of user from any help desk groups
    group_choices = list(BLANK_CHOICE_DASH)
    if user.has_perm('help_desk.add_operator'):
        group_choices.append((HELP_DESK_OPERATORS_GROUP, _(HELP_DESK_OPERATORS_GROUP)))
    if user.has_perm('help_desk.add_viewonly'):
        group_choices.append((HELP_DESK_VIEW_GROUP, _(HELP_DESK_VIEW_GROUP)))
    if user.has_perm('help_desk.add_supervisor'):
        group_choices.append((HELP_DESK_SUPERVISORS_GROUP, _(HELP_DESK_SUPERVISORS_GROUP)))
    if user.has_perm('help_desk.add_senior_staff'):
        group_choices.append((HELP_DESK_SENIOR_STAFF_GROUP, _(HELP_DESK_SENIOR_STAFF_GROUP)))
    if user.has_perm('help_desk.add_manager'):
        group_choices.append((HELP_DESK_MANAGERS_GROUP, _(HELP_DESK_MANAGERS_GROUP)))
    return group_choices


def get_day_name(day):
    """
    Get the short day name in the currently activated locale.
    :param day:
    :return:
    day 0 = Sunday
    """
    # Locale keys are 1=Sun, 2=Mon, ...
    locale_key = "ABDAY_%d" % (1 + day)
    option = getattr(locale, locale_key)
    day_name = locale.nl_langinfo(option)
    return day_name


def get_month_name(month):
    """
    Get the month's name in the currently activated locale.
    :param month:
    :return:
    """
    locale_key = "MON_%d" % month
    option = getattr(locale, locale_key)
    month_name = locale.nl_langinfo(option)
    return month_name


def format_seconds(seconds):
    """
    Return ':ss' if seconds are < 60, 'm:ss' if minutes are less than 60,
    'h:mm:ss' if more than an hour
    :param seconds:
    :return:
    """
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return '%d:%02d:%02d' % (hours, minutes, seconds)
    elif minutes:
        return '%d:%02d' % (minutes, seconds)
    else:
        return ':%02d' % seconds


def permission_names_to_objects(names):
    """
    Given an iterable of permission names (e.g. 'app_label.add_model'),
    return an iterable of Permission objects for them.
    """
    result = []
    for name in names:
        app_label, codename = name.split(".", 1)
        # Is that enough to be unique? Hope so
        try:
            result.append(Permission.objects.get(content_type__app_label=app_label,
                                                 codename=codename))
        except Permission.DoesNotExist:
            logger.exception("NO SUCH PERMISSION: %s, %s" % (app_label, codename))
            raise
    return result


def get_all_perm_names_for_group(group_name):
    """
    Looking at HELP_DESK_GROUP_PERMISSIONS, return a list of all
    the permission names that members of the named group should have.
    The list of permissions for a group in HELP_DESK_GROUP_PERMISSIONS
    can include both permission names and group names.
    """
    perm_names = set()
    for item in HELP_DESK_GROUP_PERMISSIONS[group_name]:
        if '.' in item:
            # permission name
            perm_names.add(item)
        else:
            # group name
            perm_names |= get_all_perm_names_for_group(item)
    return perm_names


def create_help_desk_groups():
    for group_name, perm_names in HELP_DESK_GROUP_PERMISSIONS.items():
        group, created = Group.objects.get_or_create(name=group_name)
        perms_to_add = permission_names_to_objects(get_all_perm_names_for_group(group_name))
        group.permissions.add(*perms_to_add)
        if not created:
            # Group already existed - make sure it doesn't have any perms we didn't want
            to_remove = set(group.permissions.all()) - set(perms_to_add)
            if to_remove:
                group.permissions.remove(*to_remove)
