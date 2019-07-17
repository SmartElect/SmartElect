from django.contrib.auth.models import User, Group, Permission
from django.contrib.auth.admin import UserAdmin, GroupAdmin

from libya_elections.admin_site import admin_site


class LibyaUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff',
                    'is_superuser')

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'email')
        }),
    )

    def get_actions(self, request):
        """"Don't allow bulk deletion."""
        return {}

    def get_form(self, request, obj=None, **kwargs):
        """Make email a required field."""
        form = super(LibyaUserAdmin, self).get_form(request, obj, **kwargs)
        email = form.base_fields['email']
        email.required = True
        return form

    def has_delete_permission(self, request, obj=None):
        """Don't allow deletion of users. (Inactivate them instead)."""
        return False


admin_site.register(User, LibyaUserAdmin)
admin_site.register(Group, GroupAdmin)
admin_site.register(Permission)
