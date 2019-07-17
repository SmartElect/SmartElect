# Django imports
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.http import require_POST

# 3rd party imports
from bread.bread import Bread, AddView as BreadAddView, \
    LabelValueReadView as BreadLabelValueReadView
from django_filters import FilterSet
from vanilla import CreateView

# This project's imports
from . import tasks
from .forms import UploadBulkSMSesForm, BroadcastForm
from .models import Broadcast, Batch
from .utils import can_approve_broadcast, is_staff
from libya_elections.filters import LibyaChoiceFilter
from libya_elections.libya_bread import PaginatedBrowseView, StaffBreadMixin
from libya_elections.utils import get_verbose_name, LoginPermissionRequiredMixin
from staff.views import StaffViewMixin


@require_POST
@login_required
@user_passes_test(is_staff)
@user_passes_test(can_approve_broadcast)
def approve_reject_broadcast(request, broadcast_id):
    """Handles the POST that approves or rejects a broadcast."""
    broadcast = get_object_or_404(Broadcast, id=broadcast_id)
    batch = broadcast.batch
    # In most cases we redirect back to the browse list.
    redirect_to = reverse('browse_broadcasts')

    if request.user == broadcast.created_by:
        messages.error(request, _('Only a different user may review your broadcast.'))
        redirect_to = reverse('read_broadcast', kwargs={'pk': broadcast.id})
    else:
        # Update broadcast.reviewed_by and save. This has to happen before updating the batch
        # status. If it doesn't, then a race condition can occur where tasks.approve_broadcast()
        # is executed before broadcast.save() is called in this thread/process. If that happens,
        # this code overwrites the change made by the task.
        if ('approve' in request.POST) or ('reject' in request.POST):
            broadcast.reviewed_by = request.user
            broadcast.save()
        if 'approve' in request.POST:
            # broadcast has been approved
            if broadcast.audience == Broadcast.CUSTOM:
                batch.status = batch.APPROVED
                batch.save()
            else:
                tasks.approve_broadcast.delay(int(broadcast_id))
            messages.success(request, _('You have approved the broadcast.'))
        elif 'reject' in request.POST:
            # broadcast has been rejected
            batch.status = batch.REJECTED
            batch.save()
            messages.success(request, _('You have rejected the broadcast.'))
        # else:
            # Neither reject nor approve in the POST? Something's fishy; ignore the POST.

    return redirect(redirect_to)


class BroadcastAddViaSimpleFormView(LoginPermissionRequiredMixin, BreadAddView):
    """View for adding a broadcast msg that can go to a center, staff, etc."""
    permission_required = 'bulk_sms.add_broadcast'
    template_name = 'bulk_sms/broadcast_add_via_form.html'

    def get_form(self, data=None, files=None, **kwargs):
        # We pass the user to the form so it can set the created_by attribute.
        return BroadcastForm(data=data, user=self.request.user)

    def form_valid(self, form):
        response = super(BroadcastAddViaSimpleFormView, self).form_valid(form)
        messages.success(self.request, _('Broadcast was created and is pending approval.'))
        return response


class BroadcastAddViaCSVUploadView(LoginPermissionRequiredMixin, StaffViewMixin, CreateView):
    """View for adding a broadcast msg sent to numbers in an uploaded CSV"""
    form_class = UploadBulkSMSesForm
    initial = {}
    template_name = 'bulk_sms/broadcast_add_via_csv.html'
    permission_required = 'bulk_sms.add_broadcast'

    def get(self, request, *args, **kwargs):
        form = self.form_class(initial=self.initial)
        context = {
            'form': form,
            'staff_page': True,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        form = UploadBulkSMSesForm(request.POST, request.FILES)
        if form.is_valid():
            form.instance.created_by = request.user
            form.save()
            messages.success(request, _("Messages are uploading in the background"))
            return redirect(reverse('browse_broadcasts'),)

        context = {
            'form': form,
            'staff_page': True,
        }
        return render(request, self.template_name, context)


class BroadcastApproveRejectView(LoginPermissionRequiredMixin, BreadLabelValueReadView):
    """View for displaying the form that allows one to approve or reject a broadcast"""
    exclude = []
    permission_required = 'bulk_sms.read_broadcast'
    fields = ((_('Sent To'), "sent_to"),
              (get_verbose_name(Broadcast, 'center'), "registration_center_as_html"),
              (None, "message"),
              (get_verbose_name(Broadcast, 'created_by'), "created_by_as_html"),
              (get_verbose_name(Broadcast, 'reviewed_by'), "reviewed_by_as_html"),
              (None, "batch"),
              (_('Status'), "status"),
              (_('Remaining Time'), "remaining_time"),
              (_('Total Messages'), "total_messages"),
              (_('Sent'), "sent"),
              (_('Errors'), "errors"),
              (_('Random Messages'), "random_messages"),
              (get_verbose_name(Broadcast, 'creation_date'), 'formatted_creation_date'),
              (get_verbose_name(Broadcast, 'modification_date'), 'formatted_modification_date'),
              )

    def get(self, request, pk):
        """Override base class to add to context and use custom template"""
        # I have to override here (rather than get_template_names()/get_context_data()) in order
        # to get access to the request object.
        broadcast = get_object_or_404(Broadcast, pk=pk)
        batch = broadcast.batch

        # I must set self.object in order to use my base class' implementation of get_context_data()
        self.object = broadcast
        context = self.get_context_data()
        context['approve_reject_url'] = reverse('approve_reject_broadcast',
                                                kwargs={'broadcast_id': broadcast.id})

        context['show_approve'] = request.user.has_perm('bulk_sms.approve_broadcast') and \
            (batch.status in (batch.PENDING, batch.REJECTED))
        context['show_reject'] = request.user.has_perm('bulk_sms.approve_broadcast') and \
            (batch.status not in (batch.REJECTED, ))

        return render(request, 'bulk_sms/broadcast_approve_reject.html', context)


class BroadcastFilterSet(FilterSet):
    status = LibyaChoiceFilter(field_name='batch__status', label=_('Status'),
                               choices=Batch.STATUS_CHOICES)
    audience = LibyaChoiceFilter(field_name='audience', label=_('Audience'),
                                 choices=Broadcast.ALL_AUDIENCES)

    class Meta:
        model = Broadcast
        fields = ['status', 'audience']


class BroadcastBrowseView(LoginPermissionRequiredMixin, PaginatedBrowseView):
    """View for browsing broadcasts; uses custom template."""
    columns = [
        (_('creation date'), 'formatted_creation_date', 'creation_date'),
        (_('Send To'), 'sent_to'),
        (_('Message'), 'message'),
        (_('Status'), 'status'),
        (_('Remaining Time'), 'remaining_time'),
        (_('Created By'), 'created_by'),
        (_('Reviewed By'), 'reviewed_by'),
    ]
    filterset = BroadcastFilterSet
    permission_required = 'bulk_sms.browse_broadcast'


class BroadcastBread(StaffBreadMixin, Bread):
    add_view = BroadcastAddViaSimpleFormView
    browse_view = BroadcastBrowseView
    exclude = ['deleted', 'created_by', 'reviewed_by', 'batch', ]
    model = Broadcast
    # The read view here is a little deceptive. It's a read-only view of the object, but it
    # includes a form with accept/reject buttons. This is more like a "Review" view than a
    # "Read" view.
    read_view = BroadcastApproveRejectView
    views = 'BRA'
