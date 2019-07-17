from django.conf.urls import url, include

from polling_reports.views import CenterClosedForElectionBread, CenterOpenBread, \
    PollingReportBread, PreliminaryVoteCountBread
from rollgen.views import StationBread
from voting.views import ElectionBread, BallotBread, CandidateBread, \
    RegistrationPeriodBread


urlpatterns = [
    # /elections:
    url(r'', include(ElectionBread().get_urls())),
    url(r'', include(BallotBread().get_urls())),
    url(r'', include(CandidateBread().get_urls())),
    url(r'', include(CenterClosedForElectionBread().get_urls())),
    url(r'', include(CenterOpenBread().get_urls())),
    url(r'', include(PollingReportBread().get_urls())),
    url(r'', include(PreliminaryVoteCountBread().get_urls())),
    url(r'', include(RegistrationPeriodBread().get_urls())),
    url(r'', include(StationBread().get_urls())),
    url(r'^rolls/', include('rollgen.urls', namespace='rollgen')),
]
