from urllib.parse import urlencode

from django.views.generic import TemplateView

from ..models import Case
from libya_elections.utils import LoginMultiplePermissionsRequiredMixin
from staff.views import StaffViewMixin


class HomeView(LoginMultiplePermissionsRequiredMixin,
               StaffViewMixin,
               TemplateView):
    template_name = 'help_desk/main.html'
    permissions = {'any': ['help_desk.read_case', 'help_desk.add_operator']}

    def get_context_data(self, **kwargs):
        context = super(HomeView, self).get_context_data(**kwargs)
        in_progress = Case.objects.filter(operator=self.request.user, end_time=None)
        if in_progress.exists():
            context['in_progress'] = in_progress
        return context


# These are all staff views, so add the staff view mixin
class PassUserToFormMixin(StaffViewMixin):
    def get_form_kwargs(self):
        kwargs = super(PassUserToFormMixin, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class GetURLMixin(object):
    """
    Mixin which can be added to ListViews to make it easier to build links by
    getting the current request's URL.

    Copied from django_bread to make our non-Bread pagination similar to Bread
    pagination.
    """

    def _get_new_url(self, **query_parms):
        """
        Return a new URL consisting of this request's URL, with any specified
        query parms updated or added.
        """
        request_kwargs = dict(self.request.GET.copy())
        request_kwargs.update(query_parms)
        return self.request.path + "?" + urlencode(request_kwargs, doseq=True)
