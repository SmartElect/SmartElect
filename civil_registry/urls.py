from django.conf import settings
from django.conf.urls import url

from civil_registry.views import GetVoterView, GetMetadataView
from libya_elections.utils import basic_auth


voter_api_db = {
    settings.VOTER_API_USER: settings.VOTER_API_PASSWORD,
}


urlpatterns = [
    # /voter:
    # The original voter API URLs did not end in '/', so we need to accept them that way.
    # But we like them with trailing '/', so accept that too.
    url(r'(?P<voter_id>\d+)/?$',
        basic_auth(GetVoterView.as_view(), voter_api_db, settings.VOTER_API_REALM),
        name='get-voter'),
    url(r'metadata/?$',
        basic_auth(GetMetadataView.as_view(), voter_api_db, settings.VOTER_API_REALM),
        name='get-metadata'),
]
