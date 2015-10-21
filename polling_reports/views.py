from bread.bread import LabelValueReadView
import django_filters

from libya_elections.libya_bread import PaginatedBrowseView, SoftDeleteBread, StaffBreadMixin
from libya_elections.utils import get_verbose_name
from polling_reports.models import CenterClosedForElection, CenterOpen, PollingReport, \
    PreliminaryVoteCount


class CenterClosedForElectionFilterSet(django_filters.FilterSet):
    class Meta:
        model = CenterClosedForElection
        fields = ['election']


class CenterClosedForElectionBrowse(PaginatedBrowseView):
    columns = (
        (get_verbose_name(CenterClosedForElection, 'election'), 'election'),
        (get_verbose_name(CenterClosedForElection, 'registration_center'), 'registration_center'),
    )
    filterset = CenterClosedForElectionFilterSet


class CenterClosedForElectionRead(LabelValueReadView):
    fields = (
        (get_verbose_name(CenterClosedForElection, 'election'), 'election_as_html'),
        (get_verbose_name(CenterClosedForElection, 'registration_center'),
         'registration_center_as_html'),
        (get_verbose_name(CenterClosedForElection, 'creation_date'),
         'formatted_creation_date'),
        (get_verbose_name(CenterClosedForElection, 'modification_date'),
         'formatted_modification_date'),
    )


class CenterClosedForElectionBread(StaffBreadMixin, SoftDeleteBread):
    model = CenterClosedForElection
    views = 'BREAD'
    browse_view = CenterClosedForElectionBrowse
    read_view = CenterClosedForElectionRead
    plural_name = 'closedcenters'


class CenterOpenFilterSet(django_filters.FilterSet):
    class Meta:
        model = CenterOpen
        fields = ['election']


class CenterOpenBrowse(PaginatedBrowseView):
    columns = (
        (get_verbose_name(CenterOpen, 'election'), 'election'),
        (get_verbose_name(CenterOpen, 'creation_date'), 'formatted_creation_date', 'creation_date'),
        (get_verbose_name(CenterOpen, 'registration_center'), 'registration_center'),
    )
    filterset = CenterOpenFilterSet


class CenterOpenRead(LabelValueReadView):
    fields = (
        (get_verbose_name(CenterOpen, 'election'), 'election_as_html'),
        (get_verbose_name(CenterOpen, 'registration_center'), 'registration_center_as_html'),
        (get_verbose_name(CenterOpen, 'phone_number'), 'formatted_phone_number_tag'),
        (get_verbose_name(CenterOpen, 'creation_date'), 'formatted_creation_date'),
        (get_verbose_name(CenterOpen, 'modification_date'), 'formatted_modification_date'),
    )


class CenterOpenBread(StaffBreadMixin, SoftDeleteBread):
    model = CenterOpen
    views = 'BR'
    browse_view = CenterOpenBrowse
    read_view = CenterOpenRead


class PollingReportFilterSet(django_filters.FilterSet):
    class Meta:
        model = PollingReport
        fields = ['election', 'period_number']


class PollingReportBrowse(PaginatedBrowseView):
    columns = (
        (get_verbose_name(PollingReport, 'election'), 'election'),
        (get_verbose_name(PollingReport, 'phone_number'), 'formatted_phone_number_tag'),
        (get_verbose_name(PollingReport, 'registration_center'), 'registration_center'),
        (get_verbose_name(PollingReport, 'period_number'), 'period_number'),
    )
    filterset = PollingReportFilterSet


class PollingReportRead(LabelValueReadView):
    fields = (
        (get_verbose_name(PollingReport, 'election'), 'election_as_html'),
        (get_verbose_name(PollingReport, 'phone_number'), 'formatted_phone_number_tag'),
        (get_verbose_name(PollingReport, 'registration_center'), 'registration_center_as_html'),
        (None, 'period_number'),
        (None, 'num_voters'),
        (get_verbose_name(PollingReport, 'creation_date'), 'formatted_creation_date'),
        (get_verbose_name(PollingReport, 'modification_date'), 'formatted_modification_date'),
    )


class PollingReportBread(StaffBreadMixin, SoftDeleteBread):
    model = PollingReport
    views = 'BR'
    browse_view = PollingReportBrowse
    read_view = PollingReportRead


class PreliminaryVoteCountFilterSet(django_filters.FilterSet):
    class Meta:
        model = PreliminaryVoteCount
        fields = ['election']


class PreliminaryVoteCountBrowse(PaginatedBrowseView):
    columns = (
        (get_verbose_name(PreliminaryVoteCount, 'election'), 'election'),
        (get_verbose_name(PreliminaryVoteCount, 'phone_number'), 'formatted_phone_number_tag'),
        (get_verbose_name(PreliminaryVoteCount, 'registration_center'), 'registration_center'),
        (get_verbose_name(PreliminaryVoteCount, 'creation_date'), 'formatted_creation_date',
         'creation_date'),
    )
    filterset = PreliminaryVoteCountFilterSet


class PreliminaryVoteCountRead(LabelValueReadView):
    fields = (
        (get_verbose_name(PreliminaryVoteCount, 'election'), 'election_as_html'),
        (get_verbose_name(PreliminaryVoteCount, 'phone_number'), 'formatted_phone_number_tag'),
        (None, 'option'),
        (None, 'num_votes'),
        (get_verbose_name(PreliminaryVoteCount, 'registration_center'),
         'registration_center_as_html'),
        (get_verbose_name(PreliminaryVoteCount, 'creation_date'),
         'formatted_creation_date'),
        (get_verbose_name(PreliminaryVoteCount, 'modification_date'),
         'formatted_modification_date'),
    )


class PreliminaryVoteCountBread(StaffBreadMixin, SoftDeleteBread):
    model = PreliminaryVoteCount
    views = 'BR'
    browse_view = PreliminaryVoteCountBrowse
    read_view = PreliminaryVoteCountRead
