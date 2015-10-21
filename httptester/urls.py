from django.conf.urls import url
from . import views


urlpatterns = (
    url(r"^$", views.generate_identity, name='httptester-index'),
    url(r"^(?P<identity>\d+)/$", views.message_tester, name='httptester'),
    url(r"^(?P<identity>\d+)/(?P<to_addr>\d+)/$", views.message_tester, name='httptester')
)
