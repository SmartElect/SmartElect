from libya_elections.admin_models import LibyaAdminModel
from libya_elections.admin_site import admin_site
from .models import Subscription


class SubscriptionAdmin(LibyaAdminModel):
    list_display = ['__str__', 'get_subscription_type_display']
    list_filter = ['subscription_type']
    raw_id_fields = ['user']


admin_site.register(Subscription, SubscriptionAdmin)
