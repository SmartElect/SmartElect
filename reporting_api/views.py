# Generates report JSON for vr-dashboard

# Python imports
import json
import logging

# 3rd party imports
from django.conf import settings
from django.http import HttpResponse

# Project imports
from libya_elections.utils import basic_auth_view
from voting.models import Election
from .encoder import DateTimeEncoder
from .reports import ELECTION_DAY_LOG_KEY, ELECTION_DAY_REPORT_KEY, \
    REGISTRATIONS_BY_COUNTRY_KEY, REGISTRATIONS_BY_OFFICE_KEY, \
    REGISTRATIONS_BY_POLLING_CENTER_KEY, REGISTRATIONS_BY_REGION_KEY, \
    REGISTRATIONS_BY_SUBCONSTITUENCY_KEY, REGISTRATIONS_METADATA_KEY, \
    REGISTRATIONS_STATS_KEY, election_key, retrieve_report


logger = logging.getLogger(__name__)

# vr-dashboard (production) and web clients (for testing) need to
# be able to grab the reports using Basic auth with well-known
# user/pass.

REPORT_USER_DB = dict()
REPORT_REALM = 'voter_api_realm'

if settings.REPORTING_API_USERNAME and settings.REPORTING_API_PASSWORD:
    REPORT_USER_DB[settings.REPORTING_API_USERNAME] = settings.REPORTING_API_PASSWORD


UNAVAILABLE_STATUS = 503
UNAVAILABLE_MSG = "Data is not yet available; please try again in a few minutes."
UNAVAILABLE_MSG_TYPE = "text/plain"


def report_unavailable():
    return HttpResponse(UNAVAILABLE_MSG, content_type=UNAVAILABLE_MSG_TYPE,
                        status=UNAVAILABLE_STATUS)


@basic_auth_view(REPORT_USER_DB, REPORT_REALM)
def registrations_report(request):
    """
    Generates a JSON-formatted registrations report for use by vr-dashboard.
    Return 503 if the report is not available.
    """
    # put together this legacy report from smaller slices in the report store
    metadata = retrieve_report(REGISTRATIONS_METADATA_KEY)
    stats = retrieve_report(REGISTRATIONS_STATS_KEY)
    by_subconstituency = retrieve_report(REGISTRATIONS_BY_SUBCONSTITUENCY_KEY)
    by_region = retrieve_report(REGISTRATIONS_BY_REGION_KEY)
    by_polling_center = retrieve_report(REGISTRATIONS_BY_POLLING_CENTER_KEY)
    by_office = retrieve_report(REGISTRATIONS_BY_OFFICE_KEY)
    by_country = retrieve_report(REGISTRATIONS_BY_COUNTRY_KEY)
    if None in [metadata, stats, by_subconstituency, by_region, by_polling_center, by_office,
                by_country]:
        # task hasn't built it yet
        return report_unavailable()

    legacy_report = dict(metadata.items() + stats.items())
    legacy_report['by_subconstituency_id'] = by_subconstituency
    legacy_report['by_region'] = by_region
    legacy_report['by_polling_center_code'] = by_polling_center
    legacy_report['by_office_id'] = by_office
    legacy_report['by_country'] = by_country
    del legacy_report['headline']

    return HttpResponse(json.dumps(legacy_report, indent=1),
                        content_type='application/json')


@basic_auth_view(REPORT_USER_DB, REPORT_REALM)
def election_day_report(request):
    """
    Create JSON-formatted election day report for use by vr-dashboard.
    Return 503 if there is no applicable election or the report is not available.
    """
    election = Election.objects.get_most_current_election()
    if election is None:
        return report_unavailable()
    t = retrieve_report(election_key(ELECTION_DAY_REPORT_KEY, election))
    if t is None:
        # task hasn't built it yet
        return report_unavailable()

    return HttpResponse(json.dumps(t, indent=1), content_type='application/json')


@basic_auth_view(REPORT_USER_DB, REPORT_REALM)
def election_day_log(request):
    """
    Generates a JSON-formatted log of all incoming daily report SMS for use by vr-dashboard.
    Return 503 if there is no applicable election or the log is not available.
    """
    election = Election.objects.get_most_current_election()
    if election is None:
        return report_unavailable()
    t = retrieve_report(election_key(ELECTION_DAY_LOG_KEY, election))
    if t is None:
        # task hasn't built it yet
        return report_unavailable()

    return HttpResponse(json.dumps(t, indent=1, cls=DateTimeEncoder),
                        content_type='application/json')
