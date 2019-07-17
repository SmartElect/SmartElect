from django.contrib import admin

from libya_elections.admin_site import admin_site

from .models import Station
from .utils import GENDER_NAMES


def gender(station):
    return GENDER_NAMES[station.gender]


class StationAdmin(admin.ModelAdmin):
    list_display = ['election', 'center', 'number', gender, 'n_registrants', ]
    search_fields = ['election__id', 'center__center_id', ]

    # Station records are not editable.
    readonly_fields = [field.name for field in Station._meta.local_fields]

    # Station records are only created programmatically via rollgen. No one is allowed to create
    # them via the admin.
    def has_add_permission(self, request):
        return False


admin_site.register(Station, StationAdmin)
