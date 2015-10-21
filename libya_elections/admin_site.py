from functools import update_wrapper

from django.contrib.admin import AdminSite
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect


class LibyaAdminSite(AdminSite):
    """Custom AdminSite that restricts entry to superusers only."""

    def has_permission(self, request):
        """Require superuser AND staff status to view the admin."""
        return request.user.is_active and request.user.is_staff and request.user.is_superuser

    def admin_view(self, view, cacheable=False):
        """
        Override superclass admin_view to provide our own auth flow.

        Specifically:
        * Return 403 if authenticated and has_permission returns False
        * Redirect to login if not authenticated
        """
        def inner(request, *args, **kwargs):
            if not self.has_permission(request):
                if request.path == reverse('admin:logout', current_app=self.name):
                    index_path = reverse('admin:index', current_app=self.name)
                    return HttpResponseRedirect(index_path)
                # Inner import to prevent django.contrib.admin (app) from
                # importing django.contrib.auth.models.User (unrelated model).
                from django.contrib.auth.views import redirect_to_login
                # Begin overriden portion here
                if not request.user.is_authenticated():
                    return redirect_to_login(
                        request.get_full_path(),
                        reverse('admin:login', current_app=self.name)
                    )
                else:
                    return HttpResponseForbidden(_('Permission Denied.'))
                # End overriden portion
            return view(request, *args, **kwargs)
        if not cacheable:
            inner = never_cache(inner)
        # We add csrf_protect here so this function can be used as a utility
        # function for any view, without having to repeat 'csrf_protect'.
        if not getattr(view, 'csrf_exempt', False):
            inner = csrf_protect(inner)
        return update_wrapper(inner, view)

admin_site = LibyaAdminSite(name='admin')
