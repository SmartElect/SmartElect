from django.contrib.admin import SimpleListFilter
from django.utils.encoding import force_text
from django.utils.translation import ugettext_lazy as _

from libya_elections.admin_site import admin_site
from libya_elections.admin_models import LibyaAdminModel
from .models import Discrepancy, SMSTrail, VumiLog


class StatusFilter(SimpleListFilter):
    title = _('Status')

    parameter_name = 'resolved'

    def lookups(self, request, model_admin):
        return (
            ('resolved', _('Resolved')),
            ('not_resolved', _('Not resolved')),
        )

    def choices(self, cl):
        for lookup, title in self.lookup_choices:
            yield {
                'selected': (self.value() == force_text(lookup) or
                             not self.value() and force_text(lookup) == "not_resolved"),
                'query_string': cl.get_query_string({
                    self.parameter_name: lookup,
                }, []),
                'display': title,
            }

    def queryset(self, request, queryset):
        if self.value() == 'resolved':
            return queryset.filter(resolved=True)
        elif self.value() == 'all':
            return queryset
        else:
            return queryset.filter(resolved=False)


class DiscrepancyAdmin(LibyaAdminModel):
    fields = ("deleted", "trail_report", "comments", "resolved")
    list_display = ("__unicode__", "resolved",)
    list_filter = (StatusFilter, )
    readonly_fields = ("trail_report",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class SMSTrailAdmin(LibyaAdminModel):
    fields = ("deleted", "report")
    readonly_fields = ("report",)

    def has_add_permission(self, request):
        return False


class VumiLogAdmin(LibyaAdminModel):
    list_display = ('logged_date', 'from_addr', 'direction', 'to_addr',
                    'content', 'is_audited')
    list_filter = ('is_audited', 'direction')

admin_site.register(Discrepancy, DiscrepancyAdmin)
admin_site.register(SMSTrail, SMSTrailAdmin)
admin_site.register(VumiLog, VumiLogAdmin)
