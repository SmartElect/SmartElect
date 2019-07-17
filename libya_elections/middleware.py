from django.contrib import messages
from django.utils.deprecation import MiddlewareMixin
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _


class GroupExpirationMiddleware(MiddlewareMixin):
    """
    Middleware which removes users from all groups after a specified expiration
    date.

    Needs to come after auth middleware because it needs request.user.
    Needs to come after message middleware because it needs request._messages.
    """

    def process_request(self, request):
        user = request.user
        if hasattr(user, 'active_range') and user.groups.exists():
            # If user has a help_desk.active_range object and is a member of any
            # group, we check to see if their staff status should be deactivated
            # by removing them from all user groups.
            today = now().date()
            end_date = user.active_range.end_date
            if end_date and end_date < today:
                # Remove staff and group access
                user.is_staff = False
                user.save()
                user.groups.clear()
                # show them a one-time message that account is not staff
                message = _('This account no longer has staff access.')
                messages.error(request, message)
