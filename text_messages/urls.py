from django.conf.urls import url

from .views import MessageListView, MessageUpdateView


urlpatterns = (
    url(r'^$', MessageListView.as_view(), name='message_list'),
    url(r'^(?P<pk>\d+)/$', MessageUpdateView.as_view(), name='message_update'),
)
