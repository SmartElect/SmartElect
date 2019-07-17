# CRUD for Help Desk Staff
from functools import reduce
import operator

from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView, FormView

from help_desk.forms import NewUserForm, UpdateUserForm
from help_desk.models import all_help_desk_groups
from help_desk.views.views import GetURLMixin, PassUserToFormMixin
from libya_elections.libya_bread import PaginatorMixin
from libya_elections.utils import LoginPermissionRequiredMixin, \
    LoginMultiplePermissionsRequiredMixin
from staff.views import StaffViewMixin


# Permissions dictionary for staff management views
staff_management_permissions = {
    # Need at least one of these permissions
    'any': [
        'help_desk.add_operator',
        'help_desk.add_supervisor',
        'help_desk.add_senior_staff',
        'help_desk.add_viewonly',
        'help_desk.add_update',
    ]
}


class StaffCreateView(LoginMultiplePermissionsRequiredMixin,
                      PassUserToFormMixin,
                      CreateView):
    """Create a new account for a help desk staffer"""
    form_class = NewUserForm
    model = User
    permissions = staff_management_permissions
    success_url = reverse_lazy('staff_list')
    template_name = 'help_desk/staff/create.html'


class StaffListView(PaginatorMixin,
                    GetURLMixin,
                    StaffViewMixin,
                    LoginMultiplePermissionsRequiredMixin,
                    ListView):
    permissions = staff_management_permissions
    queryset = None
    raise_exception = True
    template_name = 'help_desk/staff/list.html'

    def get_queryset(self):
        # Need to not construct queryset until runtime
        if self.queryset is None:
            self.queryset = User.objects.filter(groups__in=all_help_desk_groups(),
                                                is_active=True).distinct().order_by('username')
        return self.queryset


class StaffUpdateView(LoginMultiplePermissionsRequiredMixin,
                      PassUserToFormMixin,
                      UpdateView):
    form_class = UpdateUserForm
    permissions = staff_management_permissions
    queryset = User.objects.filter(is_active=True)
    success_url = reverse_lazy('staff_list')
    template_name = 'help_desk/staff/update.html'


class StaffSetPasswordView(LoginPermissionRequiredMixin,
                           StaffViewMixin,
                           FormView):
    form_class = SetPasswordForm
    permission_required = 'help_desk.change_staff_password'
    success_url = reverse_lazy('staff_list')
    template_name = 'help_desk/staff/set_password.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = get_object_or_404(User, pk=kwargs['pk'], is_active=True)
        return super(StaffSetPasswordView, self).dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super(StaffSetPasswordView, self).get_form_kwargs()
        kwargs['user'] = self.object
        return kwargs

    def form_valid(self, form):
        form.save()
        return super(StaffSetPasswordView, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super(StaffSetPasswordView, self).get_context_data(**kwargs)
        context['object'] = self.object
        return context


class StaffSearchView(PaginatorMixin,
                      GetURLMixin,
                      StaffViewMixin,
                      LoginPermissionRequiredMixin,
                      ListView):
    """This view actually searches all users. Then you can click on one of the
    users found and give them help desk permissions if you want, which is why
    it's here.
    """
    model = User
    permission_required = 'help_desk.read_case'
    queryset = User.objects.filter(is_active=True)
    template_name = 'help_desk/staff/search.html'

    def get_context_data(self, **kwargs):
        context = super(StaffSearchView, self).get_context_data(**kwargs)
        if self.request.method == 'GET':
            if 'q' in self.request.GET:
                context['q'] = self.request.GET['q']
        return context

    def get_queryset(self):
        queryset = self.queryset
        if self.request.method == 'GET':
            if self.request.GET.get('q', None):
                q = self.request.GET['q']
                search = reduce(operator.or_, [
                    Q(first_name__icontains=q),
                    Q(last_name__icontains=q),
                    Q(username__icontains=q),
                    Q(email__icontains=q),
                ])
                queryset = queryset.filter(search)
            else:
                queryset = queryset.none()
        return queryset.order_by('username')
