from __future__ import unicode_literals

from random import randint

from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.utils.translation import ugettext as _

from django_tables2 import RequestConfig

from rapidsms import settings
from . import forms
from . import storage
from .tables import MessageTable


@login_required
def generate_identity(request):
    """Simple view to generate a random identity.

    Just generates a random phone number and redirects to the
    message_tester view.

    :param request: HTTP request
    :return: An HTTPResponse
    """
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    return redirect("httptester", randint(111111, 999999))


@login_required
def message_tester(request, identity, to_addr=None):
    """The main Message Tester view.

    GET: will display the form, with the default phone number filled
    in from `identity`.

    POST: will process the form and handle it. In this case the identity
    passed to the view is ignored; the identity in the form is used to
    send any messages.

    :param request: HTTP request
    :param identity: Phone number the message will be sent from
    :param to_addr: (optional) shortcode that message will be sent to
                    (defaults to REGISTRATION_SHORT_CODE)
    :return: An HTTPResponse
    """
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    if not to_addr:
        to_addr = django_settings.REGISTRATION_SHORT_CODE
    if request.method == "POST":
        form = forms.MessageForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            identity = cd["identity"]
            to_addr = cd["to_addr"]
            if 'clear-all-btn' in request.POST:
                storage.clear_all_messages()
                messages.warning(request, _("Cleared all messages"))
            elif 'clear-btn' in request.POST:
                storage.clear_messages(identity)
                messages.warning(request, _("Cleared messages from {identity}").format(
                    identity=identity))
            else:
                if "bulk" in request.FILES:
                    for line in request.FILES["bulk"]:
                        line = line.rstrip("\n")
                        storage.store_and_queue(identity, line, to_addr)
                    messages.success(request, _("Sent bulk messages"))
                else:
                    # no bulk file was submitted, so use the "single message"
                    # field. this may be empty, which is fine, since contactcs
                    # can (and will) submit empty sms, too.
                    storage.store_and_queue(identity, cd["text"], to_addr)
                    messages.success(request, _("Sent message"))
            return redirect(message_tester, identity, to_addr)
    else:
        form = forms.MessageForm({"identity": identity, "to_addr": to_addr})

    messages_table = MessageTable(storage.get_messages(),
                                  template="httptester/table.html")
    RequestConfig(request,
                  paginate={"per_page": settings.PAGINATOR_OBJECTS_PER_PAGE})\
        .configure(messages_table)

    context = {
        'form': form,
        'messages_table': messages_table,
        'staff_page': True,
    }
    return render(request, "httptester/index.html", context)
