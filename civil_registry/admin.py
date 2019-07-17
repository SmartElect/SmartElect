from django.contrib import admin

from civil_registry.models import Citizen, DumpFile
from libya_elections.admin_site import admin_site


class CitizenAdmin(admin.ModelAdmin):
    list_display = [
        'civil_registry_id',
        'national_id',
        'format_name',
        'gender',
        'birth_date',
    ]


admin_site.register(Citizen, CitizenAdmin)
admin_site.register(DumpFile)
