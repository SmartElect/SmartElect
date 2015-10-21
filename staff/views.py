# Python imports
import os

# 3rd party imports
from bread.bread import Bread, LabelValueReadView
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django import forms
from django.forms.widgets import NullBooleanSelect
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.utils.translation import ugettext_lazy as _
from dealer.git import GitRepo
import django_filters

# This project's imports
from libya_elections.constants import LIBYA_DATETIME_FORMAT
from libya_elections.libya_bread import PaginatedBrowseView, StaffBreadMixin
from libya_elections.utils import get_comma_delimiter, get_verbose_name, format_tristate


def gitrev_view(request):
    repo = GitRepo(path=os.path.dirname(__file__))
    response = repo.git('describe --always --tags --dirty --long')
    return HttpResponse(content=response)


@login_required()
def staff_view(request):
    if not request.user.is_staff:
        return HttpResponseForbidden()
    context = {
        'ENVIRONMENT': settings.ENVIRONMENT,
        'staff_page': True,
    }
    return render(request, 'libya_site/staff.html', context)


class StaffViewMixin(object):
    """Mixin for class-based staff views to set staff_page=True in the template context"""
    def get_context_data(self, **kwargs):
        context = super(StaffViewMixin, self).get_context_data(**kwargs)
        context['staff_page'] = True
        return context


class UserFilterSet(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter(
        widget=NullBooleanSelect
    )
    is_staff = django_filters.BooleanFilter(
        widget=NullBooleanSelect
    )

    class Meta:
        model = User
        fields = ['is_active', 'is_staff']


class UserForm(forms.ModelForm):
    class Meta(object):
        model = User
        exclude = ['password', 'last_login', 'date_joined',
                   # To make a superuser, use the Django admin
                   'is_superuser',
                   # Manage user permissions using groups, not specific permissions
                   'user_permissions',
                   ]
        fields = ['username', 'email',
                  'first_name', 'last_name',
                  'groups',
                  'is_staff', 'is_active',
                  ]

    # If not staff, remove some fields
    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        if not self.instance.is_staff:
            del self.fields['groups']


class UserBrowse(PaginatedBrowseView):
    columns = [
        (_('Username'), 'username'),
        (_('Email'), 'email'),
        (_('First name'), 'first_name'),
        (_('Last name'), 'last_name'),
        (_('Staff'), 'is_staff'),
        (_('Active'), 'is_active'),
    ]
    filterset = UserFilterSet
    search_fields = ['username', 'email', 'first_name', 'last_name']
    search_terms = _('username, email, first name, or last name')


def groups_formatted(context):
    user = context['object']
    return get_comma_delimiter().join([group.name for group in user.groups.all().order_by('name')])


def date_joined_formatted(context):
    user = context['object']
    return user.date_joined.strftime(LIBYA_DATETIME_FORMAT)


class UserRead(LabelValueReadView):
    fields = ((None, 'username'),
              (None, 'email'),
              (None, 'first_name'),
              (None, 'last_name'),
              (get_verbose_name(User, 'groups'), groups_formatted),
              (get_verbose_name(User, 'is_staff'),
               lambda context: format_tristate(context['object'].is_staff)),
              (get_verbose_name(User, 'is_active'),
               lambda context: format_tristate(context['object'].is_active)),
              (get_verbose_name(User, 'date_joined'), date_joined_formatted),
              )


class UserBread(StaffBreadMixin, Bread):
    browse_view = UserBrowse
    read_view = UserRead
    form_class = UserForm
    model = User
    views = 'BRED'  # Users must use frontend to register a new account
