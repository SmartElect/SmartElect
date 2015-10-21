from __future__ import unicode_literals
from __future__ import division

from .models import Batch, Broadcast, BulkMessage
from libya_elections.admin_models import LibyaAdminModel
from libya_elections.admin_site import admin_site


class BatchAdmin(LibyaAdminModel):
    list_display = ['name', 'created_by', 'status']


class BulkMessageAdmin(LibyaAdminModel):
    list_display = ['batch', 'from_shortcode', 'phone_number', 'message']
    raw_id_fields = ['sms']


class BroadcastAdmin(LibyaAdminModel):
    list_display = ("sent_to", "message", "status", "remaining_time",
                    "created_by", "reviewed_by")
    raw_id_fields = ("center", )


admin_site.register(Broadcast, BroadcastAdmin)
admin_site.register(Batch, BatchAdmin)
admin_site.register(BulkMessage, BulkMessageAdmin)
