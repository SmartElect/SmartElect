from bread.bread import EditView, AddView, LabelValueReadView
from django import forms
from django.utils.translation import ugettext_lazy as _
from selectable.forms import AutoCompleteSelectWidget

from libya_elections.libya_bread import SoftDeleteBread, PaginatedBrowseView, StaffBreadMixin
from libya_elections.utils import get_verbose_name
from staff.lookups import StaffUserLookup
from subscriptions.models import Subscription


class SubscriptionBrowse(PaginatedBrowseView):
    columns = [
        (_("User"), 'user'),
        (_("Type of subscription"), 'get_subscription_type_display'),
    ]


class SubscriptionForm(forms.ModelForm):

    class Meta:
        fields = ['user', 'subscription_type']
        model = Subscription
        widgets = {
            'user': AutoCompleteSelectWidget(
                lookup_class=StaffUserLookup
            )
        }


class SubscriptionRead(LabelValueReadView):
    fields = [
        (_('User'), 'user'),
        (_('Type of subscription'), 'get_subscription_type_display'),
        (get_verbose_name(Subscription, 'creation_date'), 'formatted_creation_date'),
        (get_verbose_name(Subscription, 'modification_date'), 'formatted_modification_date'),
    ]


class SubscriptionEdit(EditView):
    form_class = SubscriptionForm


class SubscriptionAdd(AddView):
    form_class = SubscriptionForm


class SubscriptionsBread(StaffBreadMixin, SoftDeleteBread):
    add_view = SubscriptionAdd
    browse_view = SubscriptionBrowse
    edit_view = SubscriptionEdit
    model = Subscription
    read_view = SubscriptionRead
