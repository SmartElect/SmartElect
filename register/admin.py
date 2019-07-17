from django.contrib import admin
from django.utils.translation import ugettext as _

from libya_elections.admin_models import LibyaAdminModel
from libya_elections.admin_site import admin_site
from text_messages.models import MessageText

from .models import Person, RegistrationCenter, Registration, SMS, Blacklist, Whitelist,\
    Office, Constituency, SubConstituency


def national_id(reg):
    return reg.citizen.national_id


class BlacklistAdmin(LibyaAdminModel):
    list_display = ['phone_number', 'creation_date', 'modification_date']
    search_fields = ["phone_number"]
    readonly_fields = ['creation_date', 'modification_date']


class PersonAdmin(LibyaAdminModel):
    list_display = ['citizen']
    raw_id_fields = ['citizen']


class OfficeAdmin(LibyaAdminModel):
    list_display = ['id', 'name_english', 'name_arabic', 'region']
    search_fields = ['id', 'name_english', 'name_arabic']


class ConstituencyAdmin(LibyaAdminModel):
    list_display = ['id', 'name_english', 'name_arabic']
    search_fields = ['id', 'name_english', 'name_arabic']


class SubConstituencyAdmin(LibyaAdminModel):
    list_display = ['id', 'name_english', 'name_arabic']
    search_fields = ['id', 'name_english', 'name_arabic']


def delete_selected_except_copied_centers(modeladmin, request, queryset):
    """Custom admin action which checks to make sure user is not trying to delete a copied center.

    If a copied center is selected, user gets a warning message and no centers are deleted.
    """
    copied_ids = queryset.filter(copied_by__isnull=False).values_list('center_id', flat=True)
    if copied_ids:
        msg = _('The following centers are copied by other centers and cannot be deleted: {}. '
                'No centers were deleted.')
        modeladmin.message_user(request, msg.format(copied_ids))
    else:
        return admin.actions.delete_selected(modeladmin, request, queryset)


class RegistrationCenterAdmin(LibyaAdminModel):
    list_display = ['center_id', 'name', 'reg_open', 'office',
                    'constituency', 'subconstituency']
    list_filter = ['reg_open', 'center_type', 'office', 'constituency', 'subconstituency']
    search_fields = ["center_id", "name"]
    readonly_fields = ['copied_by_these_centers']

    date_hierarchy = 'creation_date'

    def copied_by_these_centers(self, instance):
        centers = ', '.join([str(center.center_id) for center in instance.copied_by.all()])

        return centers or _("No copies")

    def get_actions(self, request):
        actions = super(RegistrationCenterAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            # Replace it with our version
            actions['delete_selected'] = (
                delete_selected_except_copied_centers,
                'delete_selected',
                _('Permanently delete selected %(verbose_name_plural)s.')
            )
        return actions

    def get_readonly_fields(self, request, obj=None):
        """
        Don't allow changes to copy centers.
        """
        # Make sure we make a modifiable copy of the readonly fields to work with
        readonly_fields = list(super(RegistrationCenterAdmin, self).get_readonly_fields(
            request, obj))

        if obj:
            if obj.copy_of:
                # Copy centers are not editable, so mark all fields (except 'deleted') read-only
                return [field.name for field in obj._meta.local_fields
                        if field.editable and not field.name == 'deleted']

            if obj.has_copy:
                # Copied centers can't be deleted, so mark 'deleted' read-only
                if 'deleted' not in readonly_fields:
                    readonly_fields.append('deleted')

            # 'copy_of' can only be set initially, not while editing
            if 'copy_of' not in readonly_fields:
                readonly_fields.append('copy_of')

        return readonly_fields

    def has_delete_permission(self, request, obj=None):
        """Overridden to prevent deletion of RegistrationCenters that have copies."""
        delete_permission = super(RegistrationCenterAdmin, self).has_delete_permission(request, obj)
        if obj and isinstance(obj, RegistrationCenter):
            return not obj.has_copy
        else:
            return delete_permission


# See
# docs.djangoproject.com/en/dev/ref/contrib/admin/#django.contrib.admin.ModelAdmin.list_filter
# for doc on this class
class ArchivedListFilter(admin.SimpleListFilter):
    title = _('archived')
    parameter_name = 'arc'

    def lookups(self, request, model_admin):
        return (
            ('1', _('Yes')),
            ('0', _('No')),
        )

    def queryset(self, request, queryset):
        if self.value() == '0':
            return queryset.filter(archive_time=None)
        if self.value() == '1':
            return queryset.exclude(archive_time=None)


class RegistrationAdmin(LibyaAdminModel):
    list_display = ['citizen', national_id, 'registration_center', 'archive_time']
    list_display_links = [national_id]
    list_filter = [ArchivedListFilter]
    raw_id_fields = ['citizen', 'registration_center', 'sms']
    search_fields = ["registration_center__center_id", "registration_center__name"]


class SMSAdmin(LibyaAdminModel):
    list_display = ['creation_date', 'from_number', 'direction', 'to_number',
                    'citizen', 'carrier', 'msg_type', 'message_code', 'message']
    raw_id_fields = ['citizen', 'in_response_to']
    search_fields = ['from_number', 'to_number', 'carrier__name', 'msg_type', 'message']

    def get_list_display(self, *args, **kwargs):
        # Initialize the choices on the message_code field
        # We don't do it in the model def because the values are only
        # defined in the database, and we don't do it unless/until we need
        # to admin the SMS model because otherwise Django migrations think
        # the SMS message codes keep changing everytime someone with
        # different data in their database runs it.  We wait until the
        # admin calls get_list_display() to be sure someone is in the admin,
        # since it's only in the admin that it matters at all whether these
        # choices are defined.
        if not SMS._meta.get_field('message_code').choices:
            message_code_choices = [
                (msg.number, msg.label) for msg in MessageText.objects.all()
            ]
            SMS._meta.get_field('message_code').choices = message_code_choices
        return super(SMSAdmin, self).get_list_display(*args, **kwargs)


class WhiteListAdmin(LibyaAdminModel):
    list_display = ['phone_number', 'creation_date', 'modification_date']
    search_fields = ["phone_number"]
    readonly_fields = ['creation_date', 'modification_date']


admin_site.register(Blacklist, BlacklistAdmin)
admin_site.register(Person, PersonAdmin)
admin_site.register(Office, OfficeAdmin)
admin_site.register(Constituency, ConstituencyAdmin)
admin_site.register(SubConstituency, SubConstituencyAdmin)
admin_site.register(RegistrationCenter, RegistrationCenterAdmin)
admin_site.register(Registration, RegistrationAdmin)
admin_site.register(SMS, SMSAdmin)
admin_site.register(Whitelist, WhiteListAdmin)
