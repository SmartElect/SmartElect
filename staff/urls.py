from django.conf.urls import url

from .views import staff_view


urlpatterns = (
    url(r'^$', staff_view, name='staff'),
)
