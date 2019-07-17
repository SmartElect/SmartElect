from django.conf.urls import url, include
from django.views.generic.base import TemplateView

from registration.backends.default.views import ActivationView
from registration.backends.default.views import RegistrationView

from libya_site import views

urlpatterns = (
    # Public site and related URLs
    url(r'^$', views.home_page_view, name='home'),
    url(r'^check_registration/$', views.check_registration, name='check_registration'),

    # Those were the only custom views, really; the rest are related to creating
    # accounts, password management, login, changing languages, etc:
    url(r'^activate/complete/$',
        views.activation_complete,
        name='registration_activation_complete'),
    # Activation keys get matched by \w+ instead of the more specific
    # [a-fA-F0-9]{40} because a bad activation key should still get to the view;
    # that way it can return a sensible "invalid key" message instead of a
    # confusing 404.
    url(r'^activate/(?P<activation_key>\w+)/$',
        ActivationView.as_view(),
        name='registration_activate'),
    url(r'^register/$',
        RegistrationView.as_view(),
        name='registration_register'),
    url(r'^register/complete/$',
        TemplateView.as_view(template_name='registration/registration_complete.html'),
        name='registration_complete'),

    url(r'^i18n/', include('django.conf.urls.i18n')),

    url(r'', include('django.contrib.auth.urls')),
)
