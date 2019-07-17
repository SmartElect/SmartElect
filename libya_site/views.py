from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils.translation import ugettext as _

from libya_elections.utils import should_hide_public_view
from .forms import RegistrationQueryForm


def home_page_view(request):
    if should_hide_public_view(request):
        # Normally we redirect the home page to the main stats page. But
        # in this case, the stats page would just redirect to HNEC, making
        # it hard for people to check their registration, which is the other
        # main reason people come to this site. So just send them straight to
        # the check registration page. They'll still have to login, but
        # at least they'll be at the right place to do that.
        return redirect('check_registration')

    return redirect('vr_dashboard:national')


@login_required
def check_registration(request):
    context = {'check_registration_page': True}

    if request.method == 'POST':
        form = RegistrationQueryForm(request.POST)
        if form.is_valid():
            citizen = form.citizen
            context['citizen'] = citizen
            confirmed_registrations = citizen.registrations.all()
            if confirmed_registrations.count() == 1:
                registration = confirmed_registrations[0]
                context['center'] = registration.registration_center
            return render(request, 'libya_site/check_registration_results.html',
                          context)
    else:
        form = RegistrationQueryForm()
    context['form'] = form

    return render(request, 'libya_site/check_registration.html', context)


def activation_complete(request):
    messages.info(request, _("Your account has been activated.  You can login now."))
    return redirect(settings.LOGIN_URL)


def is_superuser(user):
    return user.is_superuser
