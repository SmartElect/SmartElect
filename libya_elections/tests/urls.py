from django.conf.urls import url

from .. import urls
from .utils import LoginPermissionRequiredViewRaiseExceptionFalse, \
    LoginMultiplePermissionsRequiredViewRaiseExceptionFalse, \
    LoginPermissionRequiredViewRaiseExceptionTrue, \
    LoginMultiplePermissionsRequiredViewRaiseExceptionTrue

# Additonal URLs for tests.

urlpatterns = urls.urlpatterns

urlpatterns += [
    # URLs for LoginPermissionMixinTest and LoginMultiplePermissionMixinsTest
    url(r'^foo/', LoginPermissionRequiredViewRaiseExceptionFalse.as_view(),
        name='login_permission_required_view_raise_exception_false'),
    url(r'^bar/', LoginMultiplePermissionsRequiredViewRaiseExceptionFalse.as_view(),
        name='login_multiple_permissions_required_view_raise_exception_false'),
    url(r'^boz/', LoginPermissionRequiredViewRaiseExceptionTrue.as_view(),
        name='login_permission_required_view_raise_exception_true'),
    url(r'^baz/', LoginMultiplePermissionsRequiredViewRaiseExceptionTrue.as_view(),
        name='login_multiple_permissions_required_view_raise_exception_true'),
]
