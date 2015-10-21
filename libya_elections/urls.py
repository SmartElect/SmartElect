from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.views.generic import TemplateView

from rapidsms.backends.vumi.views import VumiBackendView

from libya_elections.admin_site import admin_site
from staff.views import gitrev_view


urlpatterns = [
    # HNEC Staff applications
    url(r'^django-admin/', include(admin_site.urls)),

    url(r'^admin/', include('libya_elections.urls_admin')),
    url(r'^captcha/', include('captcha.urls')),
    url(r'^data/', include('vr_dashboard.urls', namespace='vr_dashboard')),
    url(r'^elections/', include('libya_elections.urls_elections')),
    url(r'^gitrev/$', gitrev_view, name='gitrev'),
    url(r'^health/$', TemplateView.as_view(template_name="health.html")),
    url(r'^help_desk/', include('help_desk.urls')),
    url(r'^messages/', include('text_messages.urls')),
    url(r'^registration/', include('libya_elections.urls_registration')),
    url(r'^reporting/', include('reporting_api.urls')),
    url(r'^selectable/', include('selectable.urls')),
    url(r'^sms/send/', include('bulk_sms.urls')),
    url(r'^sms/', include('libya_elections.urls_sms')),
    url(r'^staff/', include('staff.urls')),
    url(r'^voter/', include('civil_registry.urls')),

    url(r'', include('audit.urls')),
    url(r'', include('subscriptions.urls')),

    # Public web site
    url(r'', include('libya_site.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if "vumi-fake-smsc" in settings.INSTALLED_BACKENDS:
    urlpatterns += [
        url(r"^backend/vumi-fake-smsc/$",
            VumiBackendView.as_view(backend_name="vumi-fake-smsc")),
    ]
if "vumi-http" in settings.INSTALLED_BACKENDS:
    urlpatterns += [
        url(r"^backend/vumi-http/$",
            VumiBackendView.as_view(backend_name="vumi-http")),
    ]
if "libyana" in settings.INSTALLED_BACKENDS:
    urlpatterns += [
        url(r"^backend/vumi-libyana/$",
            VumiBackendView.as_view(backend_name="libyana")),
    ]
if "almadar" in settings.INSTALLED_BACKENDS:
    urlpatterns += [
        url(r"^backend/vumi-almadar/$",
            VumiBackendView.as_view(backend_name="almadar")),
    ]
if "thuraya" in settings.INSTALLED_BACKENDS:
    urlpatterns += [
        url(r"^backend/vumi-thuraya/$",
            VumiBackendView.as_view(backend_name="thuraya")),
    ]

# enable our forked httptester on testing
if settings.ENVIRONMENT != 'production':
    urlpatterns += [
        url(r'^httptester/', include('httptester.urls')),
    ]
