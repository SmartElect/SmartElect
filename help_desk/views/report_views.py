import datetime
from functools import reduce
from itertools import groupby
import operator

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from django.views.generic import FormView, ListView
from django.views.generic.edit import FormMixin
from django.views.generic.list import MultipleObjectMixin

from help_desk.forms import StatisticsReportForm, IndividualCasesReportForm, GROUP_BY_DICT
from help_desk.models import Case, FieldStaff
from help_desk.utils import get_day_name, format_seconds
from help_desk.views.views import GetURLMixin
from libya_elections.libya_bread import PaginatorMixin
from libya_elections.utils import LoginMultiplePermissionsRequiredMixin
from staff.views import StaffViewMixin


# There won't be any cases earlier than this
EARLIEST_START_DATE = datetime.date(2014, 4, 1)
# Or later than this
LATEST_START_DATE = datetime.date(2999, 12, 31)


report_permissions = {
    # Need at least one of these permissions
    'any': [
        'help_desk.read_cases',
        'help_desk.read_report',
    ]
}


def format_key_value(key_value, grouping):
    """
    :param key_value: An integer representing the part of the record we were
    interested in. How to interpret it depends on `grouping`.
    :param grouping: The way we've grouped the values
    :return: A string.
    """
    if grouping == 'days':
        return get_day_name(key_value)
    elif grouping == 'hours':
        # Hour = 0..23
        return '%d:00 - %d:59' % (int(key_value), int(key_value))
    elif grouping == 'day':
        return str(key_value.date())
    elif grouping == 'week':
        key_value = key_value.date()
        return '%s - %s' % (key_value.strftime('%x'),
                            (key_value + datetime.timedelta(days=6)).strftime('%x'))
    elif grouping == 'month':
        return key_value.strftime("%Y %b")
    elif grouping == 'year':
        return str(key_value.year)
    elif grouping == 'op':
        return get_user_model().objects.get(pk=key_value).get_full_name()
    elif grouping == 'staff':
        try:
            return FieldStaff.objects.get(pk=key_value).name
        except FieldStaff.DoesNotExist:
            return _('None')
    else:
        return key_value


class ReportMixin(PaginatorMixin):

    def get_initial(self):
        initial = self.initial.copy()
        initial.update({
            'from_date': EARLIEST_START_DATE,
            'to_date': LATEST_START_DATE,
        })
        return initial

    def get_form_kwargs(self):
        kwargs = {'initial': self.get_initial()}
        if self.request.method == 'GET':
            # Use initial data for default values, e.g. if the query
            # string doesn't have all the fields
            qdict = self.request.GET.copy()
            for k, v in kwargs['initial'].items():
                if k not in qdict:
                    if isinstance(v, list):
                        qdict.setlist(k, v)
                    else:
                        qdict[k] = v
            kwargs.update({
                'data': qdict,
            })
        return kwargs

    def get_search_query(self, q):
        """
        Given non-empty search query string `q`, return a Q() filter
        that will filter out any cases that don't match the search.
        :param q:
        :return:
        """
        search = reduce(operator.or_,
                        [
                            Q(operator__first_name__icontains=q),
                            Q(operator__last_name__icontains=q),
                            Q(operator__username__icontains=q),
                            Q(operator__email__icontains=q),
                            Q(field_staff__name__icontains=q),
                            Q(field_staff__phone_number__icontains=q),
                            Q(citizen__first_name__icontains=q),
                            Q(citizen__family_name__icontains=q),
                            Q(citizen__father_name__icontains=q),
                            Q(citizen__mother_name__icontains=q),
                            Q(citizen__grandfather_name__icontains=q),
                            Q(citizen__fbr_number__icontains=q),
                            Q(registration__registration_center__name__icontains=q),
                        ])
        try:
            number = int(q)
        except ValueError:
            pass
        else:
            search |= reduce(operator.or_,
                             [
                                 Q(citizen__national_id=number),
                                 Q(field_staff__staff_id=number),
                                 Q(registration__registration_center__center_id=number),
                                 Q(pk=number),
                             ])
        return search

    def get_case_query(self, form):
        """Builds Case query from form data."""
        q = Q()
        if form.from_date > EARLIEST_START_DATE:
            q &= Q(start_time__gte=form.from_date)
        if form.to_date < LATEST_START_DATE:
            q &= Q(start_time__lt=form.to_date)
        if self.request.GET.get('q', False):
            q &= self.get_search_query(self.request.GET['q'])
        status = form.cleaned_data['status']
        if status == 'open':
            q &= Q(end_time=None)
        elif status == 'complete':
            q &= ~Q(end_time=None)
        elif status == 'marked':
            # if recommended, still marked for review
            q &= Q(review_classification__in=[Case.FOR_REVIEW, Case.RECOMMENDED])
        elif status == 'recommended':
            q &= Q(review_classification=Case.RECOMMENDED)
        made_by = form.cleaned_data['call_made_by']
        if made_by == 'staff':
            q &= ~Q(field_staff=None)
        elif made_by == 'citizen':
            q &= Q(field_staff=None)
        return q

    def get_context_data(self, **kwargs):
        # include 'q' (search query string) in context
        return super(ReportMixin, self).get_context_data(q=self.request.GET.get('q', ''),
                                                         **kwargs)


class IndividualCasesReportView(LoginMultiplePermissionsRequiredMixin,
                                StaffViewMixin,
                                ReportMixin, GetURLMixin, FormMixin, ListView):
    form_class = IndividualCasesReportForm
    initial = {
        'trunc': None,
        'call_made_by': 'any',
        'call_outcomes': Case.ALL_CALL_OUTCOMES,
        'status': 'any',
    }
    permissions = report_permissions
    raise_exception = True
    template_name = 'help_desk/reports/cases.html'

    def get_case_query(self, form):
        caseQ = super(IndividualCasesReportView, self).get_case_query(form)
        outcomes = form.cleaned_data.get('call_outcomes', Case.ALL_CALL_OUTCOMES) \
            or Case.ALL_CALL_OUTCOMES
        if outcomes != Case.ALL_CALL_OUTCOMES:
            caseQ &= Q(call_outcome__in=outcomes)
        return caseQ

    def get_queryset(self):
        # Note: BaseListView calls .get_queryset() before .get_context_data
        # so we can set self.form here and access it in get_context_data.
        self.form = self.get_form(self.get_form_class())
        if self.form.is_valid():
            caseQ = self.get_case_query(self.form)
            qset = Case.objects.filter(caseQ)
            return qset
        return Case.objects.none()

    def get_context_data(self, **kwargs):
        return super(IndividualCasesReportView, self).get_context_data(form=self.form, **kwargs)


class StatisticsReportView(LoginMultiplePermissionsRequiredMixin,
                           StaffViewMixin,
                           ReportMixin, GetURLMixin, MultipleObjectMixin, FormView):
    form_class = StatisticsReportForm
    initial = {
        'group_by': 'day',
        'call_made_by': 'any',
        'data_to_show': 'number',
        'status': 'any',
    }
    permissions = report_permissions
    raise_exception = True
    template_name = 'help_desk/reports/stats.html'

    def get(self, request, *args, **kwargs):
        # The parent get_context_data for MultipleObjectMixin always tries to access
        # self.object_list, even if there's an object_list in kwargs.
        # To get the object_list, we need the form first...
        form_class = self.get_form_class()
        self.form = self.get_form(form_class)
        self.object_list = self.get_queryset()
        return self.render_to_response(self.get_context_data(form=self.form,
                                                             object_list=self.object_list))

    def get_queryset(self):
        """
        Return a list of lists, containing the data for the rows of the table.
        Last row is a totals row.
        """
        form = self.form
        if not form.is_valid():
            return []
        grouping = GROUP_BY_DICT[form.cleaned_data['group_by']]
        self.grouping = grouping

        cases = list(Case.objects.filter(self.get_case_query(form)).
                     extra(select={'key_value': grouping.key_select}).
                     order_by(*(grouping.order_by + ['call_outcome'])))

        if form.cleaned_data['data_to_show'] == 'number':
            self.last_column_header = _('Total')
            self.case_stats = self.number_of_cases
            self.default_value = 0
        else:
            self.last_column_header = _('Overall')
            self.case_stats = self.average_length_of_cases
            self.default_value = None

        summaries = [
            {
                'key_value': format_key_value(key_value, form.cleaned_data['group_by']),
                'stats': self.stats_row_for_list(list_of_cases),
            }
            for key_value, list_of_cases in groupby(cases, lambda case: case.key_value)
        ]

        summaries.append({
            'key_value': self.last_column_header,
            'stats': self.stats_row_for_list(cases)
        })
        return summaries

    def get_context_data(self, **kwargs):
        context = super(StatisticsReportView, self).get_context_data(**kwargs)
        if self.form.is_valid():
            # In addition to the outcome choices, the outcome is still None if the call
            # is in progress.
            context['outcome_names'] = \
                [_('In progress')] + [opt[1] for opt in Case.CALL_OUTCOME_CHOICES]
            if self.form.cleaned_data['data_to_show'] == 'number':
                context['table_title'] = _('Number of calls by outcome')
            else:
                context['table_title'] = _('Average length of calls in seconds by outcome')
            context['key_name'] = self.grouping.translated_name
            context['last_column_header'] = self.last_column_header
        return context

    def number_of_cases(self, list_of_cases):
        return len(list_of_cases)

    def average_length_of_cases(self, list_of_cases):
        number = len(list_of_cases)
        if number:
            avg = sum([case.get_length_in_seconds() for case in list_of_cases]) / number
            return format_seconds(avg)
        return None

    def stats_row_for_list(self, list_of_cases):
        """
        Return one row of the table, with statistics for this list of cases.
        The list of cases should be sorted by outcomes.
        """
        # Need to make iterable list_of_cases into a list because we're going over it twice. We also
        # need to sort the list by call_outcome because we later `groupby` call_outcome which only
        # groups results if they are contiguous.
        list_of_cases = sorted(list(list_of_cases), key=lambda case: case.call_outcome)
        # Each column is the stats for the cases for a particular outcome
        # Compute the columns for the outcomes we have cases for
        stats_dict = {
            outcome: self.case_stats(list(sub_list_of_cases))
            for outcome, sub_list_of_cases in groupby(list_of_cases, lambda case: case.call_outcome)
        }
        # Now make a list of the stats in order, filling in a default value for any
        # column we had no cases for.
        stats = [stats_dict.get(outcome, self.default_value)
                 for outcome in [None] + Case.ALL_CALL_OUTCOMES]
        # Last column is stats for the whole row
        stats.append(self.case_stats(list_of_cases))
        return stats
