# Python imports
from __future__ import division
from __future__ import unicode_literals

# Django imports
from django import template

register = template.Library()


@register.filter
def in_group(user, group_name):
    """Return True if the user is in the group, False otherwise."""
    return user.groups.filter(name=group_name).exists()


@register.filter
def can_rollgen(user):
    """Return True if the user can rollgen, False otherwise."""
    return (user.is_superuser
            or in_group(user, "rollgen_view_job")
            or in_group(user, "rollgen_create_job"))
