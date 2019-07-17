# utils for testing (as opposed to tests of utils)

# Django imports
from django.conf import settings
from django.http import HttpResponse
from django.urls import reverse
from django.views.generic.base import View

# This project's imports
from ..utils import LoginPermissionRequiredMixin, LoginMultiplePermissionsRequiredMixin


def assert_in_messages(rsp, message):
    """
    Assert that the string `message` appears somewhere in the messages that will
    be displayed as part of the response.

    :param rsp: HttpResponse from Django test client
    :param str message: String to look for in response messages
    """
    messages = [str(msg) for msg in rsp.context['messages']]
    found = any(message in msg for msg in messages)
    assert found, "Could not find string '%s' in response messages %r" % (message, messages)


class ResponseCheckerMixin(object):
    """Mixin for TestCase classes; provides response testing help"""
    def assertOK(self, response):
        """Given a response, test that it is a 200"""
        self.assertEqual(200, response.status_code)

    def assertForbidden(self, response):
        """Given a response, test that it is a 403"""
        self.assertEqual(403, response.status_code)

    def assertNotFound(self, response):
        """Given a response, test that it is a 404"""
        self.assertEqual(404, response.status_code)

    def assertRedirectsToLogin(self, response, admin_login=False):
        """Given a response, test that it is a redirect to the login page"""
        login_url = reverse('admin:login' if admin_login else settings.LOGIN_URL)
        login_url += '?next=' + response.request['PATH_INFO']
        self.assertRedirects(response, login_url)


# The four views below are for LoginPermissionMixinTest and LoginMultiplePermissionMixinsTest. They
# use different raise_exception settings to ensure that that setting has no effect on how the
# Login...Mixin classes behave.


class LoginPermissionRequiredViewRaiseExceptionFalse(LoginPermissionRequiredMixin, View):
    """View for LoginPermissionMixinTest (q.v.)"""
    permission_required = 'register.mogrify_office'
    raise_exception = False

    def get(self, request, *args, **kwargs):
        return HttpResponse('hello world')


class LoginPermissionRequiredViewRaiseExceptionTrue(LoginPermissionRequiredViewRaiseExceptionFalse):
    raise_exception = False


class LoginMultiplePermissionsRequiredViewRaiseExceptionFalse(LoginMultiplePermissionsRequiredMixin,
                                                              View):
    """View for LoginMultiplePermissionMixinsTest (q.v.)"""
    permissions = {'all': ['register.mogrify_office', 'register.frob_office']}
    raise_exception = False

    def get(self, request, *args, **kwargs):
        return HttpResponse('hello world')


class LoginMultiplePermissionsRequiredViewRaiseExceptionTrue(
    LoginMultiplePermissionsRequiredViewRaiseExceptionFalse):  # noqa
    """View for LoginMultiplePermissionMixinsTest (q.v.)"""
    raise_exception = True
