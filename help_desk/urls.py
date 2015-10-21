from django.conf.urls import include, url
from django.views.decorators.cache import never_cache

from help_desk.screens import urlpatterns as screen_urlpatterns, StartCallView
from help_desk.views.case_views import CaseDetailView, CaseUpdateView, CaseRelockView
from help_desk.views.fieldstaff_views import FieldStaffBread
from help_desk.views.report_views import IndividualCasesReportView, \
    StatisticsReportView
from help_desk.views.staff_views import StaffCreateView, StaffListView, StaffUpdateView, \
    StaffSetPasswordView, StaffSearchView
from help_desk.views.views import HomeView


urlpatterns = (
    url(r'^screen/', include(screen_urlpatterns)),
    url(r'^start_case/$', never_cache(StartCallView.as_view()), name='start_case'),

    url(r'^case/(?P<pk>\d+)/$', never_cache(CaseDetailView.as_view()), name='case_detail'),
    url(r'^case/relock/(?P<pk>\d+)/$', never_cache(CaseRelockView.as_view()), name='case_relock'),
    url(r'^case/update/(?P<case_pk>\d+)/$', never_cache(CaseUpdateView.as_view()),
        name='case_update'),

    url(r'', include(FieldStaffBread().get_urls())),

    url(r'^staff/$', never_cache(StaffListView.as_view()), name='staff_list'),
    url(r'^staff/create/$', StaffCreateView.as_view(), name='staff_create'),
    url(r'^staff/pass/(?P<pk>\d+)/$', never_cache(StaffSetPasswordView.as_view()),
        name='staff_set_password'),
    url(r'^staff/search/$', never_cache(StaffSearchView.as_view()), name='staff_search'),
    url(r'^staff/(?P<pk>\d+)/$', never_cache(StaffUpdateView.as_view()), name='staff_update'),

    url(r'^reports/cases/$', never_cache(IndividualCasesReportView.as_view()), name='report_cases'),
    url(r'^reports/stats/$', never_cache(StatisticsReportView.as_view()), name='report_stats'),

    url(r'^$', never_cache(HomeView.as_view()), name='help_desk_home'),
)
