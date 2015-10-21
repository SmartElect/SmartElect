from django.conf.urls import url, include
from staff.views import UserBread


urlpatterns = [
    # /admin:
    url(r'', include(UserBread().get_urls())),
]
