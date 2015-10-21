from django.conf.urls import url
from django.views.decorators.cache import never_cache

from views import election_day_log, election_day_report, registrations_report

urlpatterns = (
    url(r'^election_day.json$', never_cache(election_day_report)),
    url(r'^election_day_log.json$', never_cache(election_day_log)),
    url(r'^registrations.json$', never_cache(registrations_report)),
)
