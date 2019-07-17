from django.contrib import admin
from django.utils.timezone import now

from libya_elections.admin_models import LibyaAdminModel
from libya_elections.admin_site import admin_site
from voting.models import Election, Ballot, Candidate, RegistrationPeriod


class BallotInlineAdmin(admin.TabularInline):
    model = Ballot


class ElectionAdmin(LibyaAdminModel):
    fieldsets = (
        (None, {
            'fields': ['name_arabic', 'name_english',
                       'start_time', 'end_time',
                       'polling_start_time', 'polling_end_time',
                       ],
        }),
    )
    inperson_change_fieldsets = (
        (None, {
            'fields': ['name_arabic', 'name_english',
                       'start_time', 'end_time',
                       'polling_start_time', 'polling_end_time',
                       ],
        }),
    )

    inlines = [BallotInlineAdmin]
    list_display = ['name_arabic', 'name_english', 'polling_start_time', 'polling_end_time']
    list_display_links = ['name_arabic', 'name_english']
    readonly_fields = ['start_time', 'end_time']

    def get_readonly_fields(self, request, obj=None):
        # Don't allow changing an existing election's type
        fields = super(ElectionAdmin, self).get_readonly_fields(request, obj)
        if obj:
            fields.append('type')
        return fields

    def get_fieldsets(self, request, obj=None):
        if obj:
            return self.inperson_change_fieldsets
        else:
            return self.add_fieldsets


class CandidateInlineAdmin(admin.TabularInline):
    model = Candidate


class BallotAdmin(LibyaAdminModel):
    inlines = [CandidateInlineAdmin]
    list_display = ['election',
                    'internal_ballot_number',
                    'get_subconstituencies', 'name',
                    'ballot_number']
    list_display_links = ['internal_ballot_number']
    list_filter = ['election']

    def get_subconstituencies(self, obj):
        return obj.subconstituency_ids_formatted
    get_subconstituencies.short_description = "Subconstituencies"


class CandidateAdmin(LibyaAdminModel):
    list_display = ['election', 'ballot', 'candidate_number', 'name_arabic', 'name_english']
    list_display_links = ['candidate_number', 'name_arabic', 'name_english']
    list_filter = ['ballot']


class RegistrationPeriodAdmin(LibyaAdminModel):
    list_display = ['start_time', 'end_time']

    def get_readonly_fields(self, request, obj=None):
        """Don't allow editing start or end times that have passed"""
        fields = set(super(RegistrationPeriodAdmin, self).get_readonly_fields(request, obj))
        if obj:
            right_now = now()
            if obj.start_time <= right_now:
                fields.add('start_time')
            if obj.end_time <= right_now:
                fields.add('end_time')
        return list(fields)


admin_site.register(Election, ElectionAdmin)
admin_site.register(Ballot, BallotAdmin)
admin_site.register(Candidate, CandidateAdmin)
admin_site.register(RegistrationPeriod, RegistrationPeriodAdmin)
