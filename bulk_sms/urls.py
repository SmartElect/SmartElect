from django.conf.urls import url, include

from .views import approve_reject_broadcast, BroadcastBread, BroadcastAddViaCSVUploadView


urlpatterns = (
    # /sms/send (for bulk SMS)
    url(r'', include(BroadcastBread().get_urls())),
    url(r'^broadcast/upload/$', BroadcastAddViaCSVUploadView.as_view(),
        name='upload_broadcast'),
    url(r'^broadcast/approve_reject/(?P<broadcast_id>\d+)/$', approve_reject_broadcast,
        name='approve_reject_broadcast'),
)
