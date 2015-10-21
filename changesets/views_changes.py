from bread.bread import Bread
from django_filters import FilterSet
from django.utils.translation import ugettext_lazy as _
from changesets.models import ChangeRecord, Changeset
from libya_elections.libya_bread import StaffBreadMixin, PaginatedBrowseView


class ChangeRecordFilterSet(FilterSet):
    class Meta:
        model = ChangeRecord
        fields = ['changeset']


class ChangeRecordBrowse(PaginatedBrowseView):
    columns = [
        (_('National ID'), 'citizen__national_id'),
        (_('Name'), 'citizen'),
        (_('Changed'), 'changed_yes_no'),
        (_('Change'), 'get_change_display'),
        (_('From'), 'display_from_center'),
        (_('To'), 'display_to_center'),
    ]
    filterset = ChangeRecordFilterSet

    def get_changeset(self):
        if not hasattr(self, "_changeset"):
            changeset_pk = self.request.GET.get('changeset', None)
            if changeset_pk:
                self._changeset = Changeset.objects.get(pk=changeset_pk)
            else:
                self._changeset = None
        return self._changeset

    def get_context_data(self, **kwargs):
        context = super(ChangeRecordBrowse, self).get_context_data(**kwargs)
        context['changeset'] = self.get_changeset()
        return context

    def get_queryset(self):
        qset = super(ChangeRecordBrowse, self).get_queryset()
        if self.get_changeset():
            qset = qset.filter(changeset=self.get_changeset())
        return qset.select_related('citizen', 'from_center', 'to_center')


class ChangeRecordBread(StaffBreadMixin, Bread):
    browse_view = ChangeRecordBrowse
    model = ChangeRecord
    views = 'B'
