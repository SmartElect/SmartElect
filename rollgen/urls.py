# Python imports
from __future__ import division
from __future__ import unicode_literals

# Django imports
from django.conf.urls import url

# Project imports
from .constants import JOB_NAME_REGEX, OFFICE_ID_REGEX, PDF_FILENAME_REGEX, ZIP_FILENAME_REGEX
from .views import overview_view, serve_pdf, serve_zip, new_view, polling_csv_view, \
    browse_job_offices_view, browse_job_centers_view, browse_office_view

urlpatterns = (
    url(r'^$', overview_view, name='overview'),
    url(r'^polling_csv/$', polling_csv_view, name='polling_csv'),
    url(r'^new/$', new_view, name='new'),

    url(r'^job/{}/$'.format(JOB_NAME_REGEX), browse_job_offices_view,
        name='browse_job_offices'),
    url(r'^job/{}/centers?/$'.format(JOB_NAME_REGEX), browse_job_centers_view,
        name='browse_job_centers'),
    url(r'^job/{}/{}$'.format(JOB_NAME_REGEX, OFFICE_ID_REGEX), browse_office_view,
        name='browse_office_view'),
    url(r'^job/{}/{}/{}$'.format(JOB_NAME_REGEX, OFFICE_ID_REGEX, PDF_FILENAME_REGEX),
        serve_pdf, name='serve_pdf'),
    url(r'^job/{}/{}$'.format(JOB_NAME_REGEX, ZIP_FILENAME_REGEX), serve_zip, name='serve_zip'),
    )