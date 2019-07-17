# 3rd party imports
from bread.bread import LabelValueReadView
import django_filters
from django.utils.translation import ugettext_lazy as _

# This project imports
from .forms import RegistrationPeriodAddForm
from .models import Election, Ballot, Candidate, RegistrationPeriod
from libya_elections.libya_bread import PaginatedBrowseView, SoftDeleteBread, StaffBreadMixin
from libya_elections.utils import LoginPermissionRequiredMixin, \
    get_verbose_name
from register.models import SubConstituency
from register.views import AllNamedThingsFilter


class ElectionBrowse(PaginatedBrowseView):
    columns = [
        (_('Start'), 'formatted_polling_start_time', 'polling_start_time'),
        (_('Name (en)'), 'name_english'),
        (_('Name (ar)'), 'name_arabic'),
    ]
    search_fields = ['name_english', 'name_arabic']
    search_terms = _('Election name in English or Arabic')


class ElectionReadView(LoginPermissionRequiredMixin, LabelValueReadView):
    permission_required = "voting.read_election"
    fields = ((None, 'name_english'),
              (None, 'name_arabic'),
              (get_verbose_name(Election, 'polling_start_time'), 'formatted_polling_start_time'),
              (get_verbose_name(Election, 'polling_end_time'), 'formatted_polling_end_time'),
              (get_verbose_name(Election, 'creation_date'), 'formatted_creation_date'),
              (get_verbose_name(Election, 'modification_date'), 'formatted_modification_date'),
              )


class ElectionBread(StaffBreadMixin, SoftDeleteBread):
    browse_view = ElectionBrowse
    read_view = ElectionReadView
    model = Election


class BallotFilterSet(django_filters.FilterSet):
    subconstituencies = AllNamedThingsFilter(filter_by_model=SubConstituency)

    class Meta:
        model = Ballot
        fields = ['election', 'subconstituencies', 'ballot_type']


class BallotBrowse(PaginatedBrowseView):
    filterset = BallotFilterSet


class BallotReadView(LabelValueReadView):
    fields = ((get_verbose_name(Ballot, 'election'), 'election_as_html'),
              (get_verbose_name(Ballot, 'subconstituencies'), 'subconstituencies_as_html'),
              (None, 'internal_ballot_number'),
              (get_verbose_name(Ballot, 'ballot_type'), 'get_ballot_type_display'),
              (None, 'num_seats'),
              (get_verbose_name(Ballot, 'creation_date'), 'formatted_creation_date'),
              (get_verbose_name(Ballot, 'modification_date'), 'formatted_modification_date'),
              )


class BallotBread(StaffBreadMixin, SoftDeleteBread):
    browse_view = BallotBrowse
    read_view = BallotReadView
    model = Ballot


class CandidateFilterSet(django_filters.FilterSet):
    ballot__subconstituencies = AllNamedThingsFilter(filter_by_model=SubConstituency)

    class Meta:
        model = Candidate
        fields = ['ballot', 'ballot__subconstituencies']


class CandidateBrowse(PaginatedBrowseView):
    columns = [
        (_('Ballot'), 'ballot__name'),
        (_('Number'), 'candidate_number'),
        (_('Name (en)'), 'name_english'),
        (_('Name (ar)'), 'name_arabic'),
    ]
    filterset = CandidateFilterSet
    search_fields = ['name_english', 'name_arabic']
    search_terms = _('Candidate name in English or Arabic')


class CandidateRead(LabelValueReadView):
    fields = ((None, 'name_arabic'),
              (None, 'name_english'),
              (None, 'candidate_number'),
              (get_verbose_name(Candidate, 'ballot'), 'ballot_as_html'),
              (get_verbose_name(Candidate, 'creation_date'), 'formatted_creation_date'),
              (get_verbose_name(Candidate, 'modification_date'), 'formatted_modification_date'),
              )


class CandidateBread(StaffBreadMixin, SoftDeleteBread):
    browse_view = CandidateBrowse
    read_view = CandidateRead
    model = Candidate
    views = 'BREAD'


class RegistrationPeriodBrowse(PaginatedBrowseView):
    columns = (
        (get_verbose_name(RegistrationPeriod, 'start_time'), 'formatted_start_time', 'start_time'),
        (get_verbose_name(RegistrationPeriod, 'end_time'), 'formatted_end_time', 'end_time'),
    )


class RegistrationPeriodReadView(LabelValueReadView):
    fields = (
        (get_verbose_name(RegistrationPeriod, 'start_time'), 'formatted_start_time'),
        (get_verbose_name(RegistrationPeriod, 'end_time'), 'formatted_end_time'),
        (get_verbose_name(RegistrationPeriod, 'creation_date'), 'formatted_creation_date'),
        (get_verbose_name(RegistrationPeriod, 'modification_date'), 'formatted_modification_date'),
    )


class RegistrationPeriodBread(StaffBreadMixin, SoftDeleteBread):
    browse_view = RegistrationPeriodBrowse
    # Override default so that start/end timestamps are not split into date/time
    # for display (unlike Edit)
    read_view = RegistrationPeriodReadView
    model = RegistrationPeriod
    form_class = RegistrationPeriodAddForm
