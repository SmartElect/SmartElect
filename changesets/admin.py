# Uncomment locally for debugging,
# but don't commit that way.

# from django.contrib import admin
#
# from libya_elections.admin_site import admin_site
# from .models import Changeset, ChangeRecord
#
#
# class ChangesetAdmin(admin.ModelAdmin):
#     list_display = ['name', 'status',
#                     'number_of_approvals',
#                     'creation_date', 'execution_start_time',
#                     'how_to_select', 'change',
#                     ]
#     raw_id_fields = ['approvers',
#                      'other_changeset',
#                      'rollback_changeset',
#                      'selected_centers',
#                      'target_center',
#                      ]
#
#
# class ChangeRecordAdmin(admin.ModelAdmin):
#     list_display = ['changeset', 'changed', 'citizen', 'change', 'from_center', 'to_center']
#
#
# admin_site.register(Changeset, ChangesetAdmin)
# admin_site.register(ChangeRecord, ChangeRecordAdmin)
