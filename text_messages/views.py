# CRU for text messages (no D)
from django.core.urlresolvers import reverse_lazy
from django.views.generic import ListView, UpdateView

from libya_elections.utils import LoginPermissionRequiredMixin
from staff.views import StaffViewMixin

from text_messages.forms import MessageTextForm
from text_messages.models import MessageText


class MessageListView(LoginPermissionRequiredMixin, StaffViewMixin, ListView):
    model = MessageText
    permission_required = "text_messages.change_messagetext"


class MessageUpdateView(LoginPermissionRequiredMixin, StaffViewMixin, UpdateView):
    form_class = MessageTextForm
    model = MessageText
    permission_required = "text_messages.change_messagetext"
    success_url = reverse_lazy('message_list')

    def form_valid(self, form):
        self.object.last_updated_by = self.request.user
        return super(MessageUpdateView, self).form_valid(form)
