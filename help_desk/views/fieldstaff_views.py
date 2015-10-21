# BREAD for Field Staff
from django.utils.translation import ugettext_lazy as _

from bread.bread import LabelValueReadView, EditView, AddView
import django_filters

from libya_elections.libya_bread import PaginatedBrowseView, SoftDeleteBread, StaffBreadMixin
from libya_elections.utils import format_tristate, get_verbose_name
from help_desk.models import FieldStaff


class FieldStaffFilterSet(django_filters.FilterSet):
    class Meta:
        model = FieldStaff
        fields = ['suspended', ]


class FieldStaffBrowse(PaginatedBrowseView):
    filterset = FieldStaffFilterSet
    columns = (
        (get_verbose_name(FieldStaff, 'staff_id'), 'staff_id'),
        (get_verbose_name(FieldStaff, 'name'), 'name'),
        (get_verbose_name(FieldStaff, 'phone_number'), 'formatted_phone_number_tag'),
        (get_verbose_name(FieldStaff, 'suspended'), 'suspended'),
    )
    search_fields = ['staff_id', 'name', 'phone_number']
    search_terms = _('Staff Id, Name, or Phone Number')


class FieldStaffRead(LabelValueReadView):
    fields = (
        (None, 'staff_id'),
        (None, 'name'),
        (get_verbose_name(FieldStaff, 'phone_number'), 'formatted_phone_number_tag'),
        (get_verbose_name(FieldStaff, 'suspended'),
         lambda context: format_tristate(context['object'].suspended)),
        (get_verbose_name(FieldStaff, 'creation_date'), 'formatted_creation_date'),
        (get_verbose_name(FieldStaff, 'modification_date'), 'formatted_modification_date'),
    )


class FieldStaffEdit(EditView):
    def get_form(self, data=None, files=None, **kwargs):
        form = super(FieldStaffEdit, self).get_form(data, files, **kwargs)
        if not self.request.user.has_perm('help_desk.suspend_fieldstaff'):
            del form.fields['suspended']
        return form


class FieldStaffAdd(AddView):
    def get_form(self, data=None, files=None, **kwargs):
        form = super(FieldStaffAdd, self).get_form(data, files, **kwargs)
        if not self.request.user.has_perm('help_desk.suspend_fieldstaff'):
            del form.fields['suspended']
        return form


class FieldStaffBread(StaffBreadMixin, SoftDeleteBread):
    model = FieldStaff
    views = 'BREA'
    plural_name = 'fieldstaff'
    browse_view = FieldStaffBrowse
    read_view = FieldStaffRead
    edit_view = FieldStaffEdit
    add_view = FieldStaffAdd
