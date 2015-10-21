from bread.bread import LabelValueReadView, EditView
from django import forms
from django.contrib import messages
from django.utils.translation import ungettext, ugettext_lazy as _
from django_filters import FilterSet

from audit.models import Discrepancy, VumiLog, SMSTrail
from libya_elections.libya_bread import PaginatedBrowseView, SoftDeleteBread, StaffBreadMixin
from libya_elections.utils import get_verbose_name


class DiscrepancyFilterSet(FilterSet):
    class Meta:
        model = Discrepancy
        fields = ['resolved', ]


class DiscrepanciesBrowse(PaginatedBrowseView):
    columns = [
        (get_verbose_name(Discrepancy, 'creation_date'), 'formatted_creation_date',
         'creation_date'),
        (_("Direction"), 'get_direction_display'),
        (_("From"), 'get_from'),
        (_("To"), 'get_to'),
        (get_verbose_name(Discrepancy, 'resolved'), 'resolved'),
    ]
    filterset = DiscrepancyFilterSet
    search_fields = [
        'trail__sms__from_number', 'trail__sms__to_number', 'trail__sms__message',
        'trail__vumi__from_addr', 'trail__vumi__to_addr', 'trail__vumi__content',
    ]
    search_terms = _("source number, destination number, or message")

    def get(self, request, *args, **kwargs):
        # Default to "resolved=False"
        if 'resolved' not in request.GET:
            request.GET = request.GET.copy()  # make editable
            request.GET['resolved'] = '3'  # choices are 1=any, 2=True, 3=False

        response = super(DiscrepanciesBrowse, self).get(request, *args, **kwargs)

        audited = SMSTrail.objects.count()
        audited_messages = ungettext(
            '%(count)d message was audited.',
            '%(count)d messages were audited.',
            audited
        ) % {'count': audited}
        messages.info(request, audited_messages)

        discrepancies = Discrepancy.objects.filter(resolved=False).count()
        if discrepancies:
            discrepancies_found = ungettext(
                'There was %(count)d discrepancy found.',
                'There were %(count)d discrepancies found.',
                discrepancies
            ) % {'count': discrepancies}
            messages.error(request, discrepancies_found)
        return response

    def get_queryset(self):
        qset = super(DiscrepanciesBrowse, self).get_queryset()
        return qset.select_related('trail', 'trail__sms', 'trail__vumi')


def get_direction(ctx):
    return dict(VumiLog.DIRECTION_CHOICES)[ctx['object'].trail.direction]


def get_datetime(ctx):
    return ctx['object'].trail.datetime


class DiscrepanciesRead(LabelValueReadView):

    fields = [
        (_("Direction"), get_direction),
        (_("Message in registration system"), 'sms_as_html'),
        (_("Message to/from the mobile network operator"), 'vumilog_as_html'),
        (None, 'comments'),
        (None, 'resolved'),
        (get_verbose_name(Discrepancy, 'creation_date'),
         'formatted_creation_date'),
        (get_verbose_name(Discrepancy, 'modification_date'),
         'formatted_modification_date'),
    ]


class DiscrepancyForm(forms.ModelForm):
    class Meta:
        model = Discrepancy
        fields = ['comments', 'resolved']


class DiscrepanciesEdit(EditView):
    form_class = DiscrepancyForm


class DiscrepanciesBread(StaffBreadMixin, SoftDeleteBread):
    browse_view = DiscrepanciesBrowse
    edit_view = DiscrepanciesEdit
    model = Discrepancy
    read_view = DiscrepanciesRead
    plural_name = "discrepancies"
    views = 'BRE'


class VumiLogRead(LabelValueReadView):
    fields = [
        (get_verbose_name(VumiLog, 'from_addr'), 'from_number_formatted_tag'),
        (get_verbose_name(VumiLog, 'direction'), 'get_direction_display'),
        (get_verbose_name(VumiLog, 'to_addr'), 'to_number_formatted_tag'),
        (None, 'content'),
        (get_verbose_name(VumiLog, 'creation_date'), 'formatted_creation_date'),
        (get_verbose_name(VumiLog, 'modification_date'), 'formatted_modification_date'),
    ]

    def get_context_data(self, **kwargs):
        """Add a back_url so we can link back to the associated discrepancy"""
        context = super(VumiLogRead, self).get_context_data(**kwargs)
        context['back_url'] = self.get_object().smstrail.discrepancy.get_absolute_url()
        return context


class VumiLogsBread(StaffBreadMixin, SoftDeleteBread):
    model = VumiLog
    read_view = VumiLogRead
    views = 'R'
