# 3rd party
from django.conf.urls import url, include

# Our own modules
from civil_registry.views import CitizenBread
from register.views import RegistrationCenterBread, OfficeBread, ConstituencyBread, \
    RegistrationBread, SubconstituencyBread, delete_all_copy_centers, download_centers_csv, \
    UploadCenterView


urlpatterns = (
    # /registration:
    url(r'^centers/', include(RegistrationCenterBread().get_urls(prefix=False))),
    url(r'', include(OfficeBread().get_urls())),
    url(r'', include(ConstituencyBread().get_urls())),
    url(r'', include(SubconstituencyBread().get_urls())),
    url(r'', include(CitizenBread().get_urls())),
    url(r'^changes/', include('changesets.urls')),
    url(r'', include(RegistrationBread().get_urls())),

    # Non-BREAD operations on registration centers
    url(r'^centers/delete-all-copy-centres/$', delete_all_copy_centers,
        name='delete-all-copy-centers'),
    url(r'^centers/download-centres-csv/$', download_centers_csv,
        name='download-centers-csv'),
    url(r'^centers/upload-centres-csv/$', UploadCenterView.as_view(),
        name='upload-centers-csv'),
)
