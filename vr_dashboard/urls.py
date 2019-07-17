from django.conf.urls import url

from .views.views import csv_daily_report, csv_report, election_day, election_day_center, \
    reports, center_csv_report, phone_csv_report, \
    election_day_center_n, election_day_office_n, election_day_preliminary, national, offices, \
    offices_detail, redirect_to_national, regions, sms, subconstituencies, weekly, election_day_hq

from .views.phone_tool import matching_phones, phone_history, phone_message_tool, whitelist_phone

app_name = 'vr_dashboard'
urlpatterns = (
    url(r'^$', redirect_to_national),
    url(r'^election_day/$', election_day, name='election-day'),
    url(r'^election_day/hq/$', election_day_hq, name='election-day-hq'),
    url(r'^election_day/preliminary/$', election_day_preliminary, name='election-day-preliminary'),
    url(r'^election_day/center/$', election_day_center, name='election-day-center'),
    url(r'^election_day/center/(?P<center_id>[\d]+)/$', election_day_center_n,
        name='election-day-center-n'),
    url(r'^election_day/office/(?P<office_id>[\d]+)/$', election_day_office_n,
        name='election-day-office-n'),
    url(r'^national/$', national, name='national'),
    url(r'^offices/$', offices, name='offices'),
    url(r'^offices_detail/$', offices_detail, name='offices-detail'),
    url(r'^regions/$', regions, name='regions'),
    url(r'^sms/$', sms, name='sms'),
    url(r'^reports/$', reports, name='reports'),
    url(r'^subconstituencies/$', subconstituencies, name='subconstituencies'),
    url(r'^weekly/$', weekly, name='weekly'),
    url(r'^csv/$', csv_report, name='csv'),
    url(r'^daily_csv/$', csv_daily_report, name='daily-csv'),
    url(r'^daily_csv/(?P<from_date>\d{2}/\d{2}/\d{4})/(?P<to_date>\d{2}/\d{2}/\d{4})/$',
        csv_daily_report, name='daily-csv-with-dates'),
    url(r'^center_csv/$', center_csv_report, name='center-csv'),
    url(r'^phone_csv/$', phone_csv_report, name='phone-csv'),
    url(r'^phone_tool/$', phone_message_tool, name='phone-message-tool'),
    url(r'^phone_tool/matching_phones/$', matching_phones, name='search-phones'),
    url(r'^phone_tool/phone_history/$', phone_history, name='phone-history'),
    url(r'^phone_tool/whitelist_phone/$', whitelist_phone, name='whitelist-phone')
)
