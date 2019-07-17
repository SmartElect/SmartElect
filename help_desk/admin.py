from django.contrib import admin

from libya_elections.admin_models import LibyaAdminModel
from libya_elections.admin_site import admin_site

from .models import Case, ScreenRecord, FieldStaff, Update


class UpdateAdminInline(admin.TabularInline):
    model = Update
    extra = 0
    raw_id_fields = ['user']


class ScreenAdminInline(admin.TabularInline):
    model = ScreenRecord
    extra = 0


class CaseAdmin(LibyaAdminModel):
    inlines = [ScreenAdminInline, UpdateAdminInline]
    list_display = ['start_time', 'end_time', 'current_screen', 'call_outcome', 'citizen',
                    'operator', 'field_staff']
    list_filter = ['call_outcome', 'review_classification', 'reason_marked']
    search_fields = ['operator__last_name', 'operator__first_name',
                     'citizen__family_name', 'citizen__first_name', 'citizen__father_name',
                     'citizen__grandfather_name', 'citizen__mother_name',
                     'citizen__national_id']
    raw_id_fields = ['citizen', 'current_screen', 'operator', 'field_staff',
                     'registration']


class FieldStaffAdmin(LibyaAdminModel):
    list_display = ['name', 'staff_id', 'phone_number', 'suspended']
    list_filter = ['suspended']
    search_fields = ['name', 'staff_id', 'phone_number']


admin_site.register(Case, CaseAdmin)
admin_site.register(FieldStaff, FieldStaffAdmin)
