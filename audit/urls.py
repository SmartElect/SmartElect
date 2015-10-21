from django.conf.urls import url, include

from audit.views import DiscrepanciesBread, VumiLogsBread


urlpatterns = [
    url(r'^sms/auditing/discrepancies/', include(DiscrepanciesBread().get_urls(prefix=False))),
    url(r'^sms/auditing/vumilogs/', include(VumiLogsBread().get_urls(prefix=False))),
]
