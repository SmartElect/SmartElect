# Django imports
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView, CreateView, View

# This project's imports
from help_desk.forms import AddCaseUpdateForm
from help_desk.models import Case, Update
from help_desk.views.views import PassUserToFormMixin
from libya_elections.utils import LoginPermissionRequiredMixin
from staff.views import StaffViewMixin


class CaseDetailView(LoginPermissionRequiredMixin,
                     StaffViewMixin,
                     DetailView):
    model = Case
    permission_required = 'help_desk.read_case'
    context_object_name = 'case'
    template_name = 'help_desk/cases/case_detail.html'


class CaseRelockView(LoginPermissionRequiredMixin,
                     StaffViewMixin,
                     View):
    http_method_names = ['post']
    permission_required = 'help_desk.cancel_registration'

    def post(self, request, *args, **kwargs):
        case = get_object_or_404(Case, pk=kwargs['pk'])
        case.relock_registration()
        return redirect(case.get_absolute_url())


class CaseUpdateView(LoginPermissionRequiredMixin,
                     PassUserToFormMixin,
                     CreateView):
    """
    This doesn't update a case record, it adds an "update" record that is
    linked to the case.
    """
    form_class = AddCaseUpdateForm
    model = Update
    permission_required = 'help_desk.add_update'
    template_name = 'help_desk/cases/update_form.html'

    def get_success_url(self):
        return self.get_case().get_absolute_url() + '#updates'

    def form_valid(self, form):
        form.save()
        return super(CaseUpdateView, self).form_valid(form)

    def get_case(self):
        if not hasattr(self, '_case'):
            self._case = get_object_or_404(Case, pk=self.kwargs['case_pk'])
        return self._case

    def get_context_data(self, **kwargs):
        context = super(CaseUpdateView, self).get_context_data(**kwargs)
        context['case'] = self.get_case()
        return context

    def get_form_kwargs(self):
        kwargs = super(CaseUpdateView, self).get_form_kwargs()
        if not self.object:
            self.object = Update(
                case=self.get_case(),
                kind=Update.COMMENT,
                user=self.request.user,
            )
        kwargs.update({'instance': self.object})
        return kwargs
