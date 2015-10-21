from libya_elections.admin_models import LibyaAdminModel
from libya_elections.admin_site import admin_site

from .models import StaffPhone, CenterClosedForElection, CenterOpen, PollingReport, \
    PreliminaryVoteCount


class StaffPhoneAdmin(LibyaAdminModel):
    search_fields = ("phone_number", "registration_center__center_id", "registration_center__name")
    list_display = ("phone_number", "registration_center")
    raw_id_fields = ("registration_center", )


class CenterOpenAdmin(LibyaAdminModel):
    search_fields = ("registration_center__center_id", "registration_center__name", "phone_number")
    list_display = ("creation_date", "phone_number", "registration_center")
    raw_id_fields = ("registration_center", )


class PollingReportAdmin(LibyaAdminModel):
    list_display = ('phone_number', 'registration_center', 'period_number', 'num_voters')
    search_fields = ('phone_number', 'registration_center__center_id', 'registration_center__name')


class PreliminaryVoteCountAdmin(LibyaAdminModel):
    list_display = ('election', 'registration_center', 'creation_date', 'option', 'num_votes')
    search_fields = ('phone_number', 'registration_center__center_id')


class CenterClosedForElectionAdmin(LibyaAdminModel):
    list_display = ('registration_center', 'election')
    search_fields = ('registration_center__center_id', 'election__name_arabic',
                     'election__name_english')

admin_site.register(StaffPhone, StaffPhoneAdmin)
admin_site.register(CenterOpen, CenterOpenAdmin)
admin_site.register(PollingReport, PollingReportAdmin)
admin_site.register(PreliminaryVoteCount, PreliminaryVoteCountAdmin)
admin_site.register(CenterClosedForElection, CenterClosedForElectionAdmin)
