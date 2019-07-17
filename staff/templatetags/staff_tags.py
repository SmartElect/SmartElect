from django import template

from libya_elections.utils import should_see_staff_view


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


@register.filter
def can_see_staff_link(user):
    """
    Return True if the user should see the staff view.

    Example usage:  {{ user|can_see_staff_link }}
    """
    return should_see_staff_view(user)
