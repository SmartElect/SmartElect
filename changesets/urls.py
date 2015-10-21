from django.conf.urls import url, include

from changesets.views_changes import ChangeRecordBread
from changesets.views_changeset import ChangesetBread, ApproveView


# Under /registration/registrations from urls_registration.py:
from changesets.views_uploadedcitizens import UploadedCitizenBread


change_record_bread = ChangeRecordBread()
uploaded_citizens_bread = UploadedCitizenBread()

urlpatterns = [
    url(r'^approve/(?P<pk>\d+)/$', ApproveView.as_view(), name="approve_changeset"),
    url(r'^changes/$', change_record_bread.get_browse_view(), name="browse_changerecords"),
    url(r'^uploaded_citizens/$', uploaded_citizens_bread.get_browse_view(),
        name="browse_uploadedcitizens"),

    url(r'^', include(ChangesetBread().get_urls(prefix=False))),
]
