from django.conf.urls import url, include
from subscriptions.views import SubscriptionsBread


urlpatterns = [
    url(r'^sms/auditing/subscriptions/', include(SubscriptionsBread().get_urls(prefix=False)))
]
