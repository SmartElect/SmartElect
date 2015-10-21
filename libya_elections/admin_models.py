from django.contrib import admin
from django.utils.translation import ugettext_lazy as _


class LibyaAdminModel(admin.ModelAdmin):
    """
    Admin model that implements the following features:

    1. Label bulk-deletion as 'Permanent'
    2. Show soft-deleted objects
    """

    def get_actions(self, request):
        actions = super(LibyaAdminModel, self).get_actions(request)
        if 'delete_selected' in actions:
            actions['delete_selected'][0].short_description = _(
                'Permanently delete selected %(verbose_name_plural)s.')
        return actions

    def get_queryset(self, request):
        """
        Return a queryset of all objects (including deleted ones).
        """
        qs = self.model.objects.unfiltered()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs
