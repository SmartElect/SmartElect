from django.contrib.auth.decorators import user_passes_test
from django.db.models import Q
from django.http import HttpResponseBadRequest, HttpResponseNotFound, HttpResponseRedirect
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import ugettext as _

from libya_elections.phone_numbers import is_valid_phone_number
from polling_reports.models import StaffPhone
from register.models import RegistrationCenter, SMS, Whitelist
from register.utils import is_center_id_valid
from reporting_api.codings import MESSAGE_TYPES
from vr_dashboard.forms import get_invalid_center_error_string, PhoneAndMessageQueryForm


@user_passes_test(lambda user: user.is_staff)
def phone_message_tool(request):
    if request.method == 'POST':
        form = PhoneAndMessageQueryForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['phone_number']:
                query_args = '?phone=%s' % form.cleaned_data['phone_number']
                return HttpResponseRedirect(reverse('vr_dashboard:phone-history') + query_args)
            else:
                query_args = '?center_id=%s' % form.cleaned_data['center_id']
                return HttpResponseRedirect(reverse('vr_dashboard:search-phones') + query_args)
    else:
        form = PhoneAndMessageQueryForm()

    context = {
        'form': form,
        'phone_tool_page': True,
        'staff_page': True,
    }
    return render(request, 'vr_dashboard/phone_tool/query_form.html', context)


def get_phone_tool_error(error_class, request, error_msg):
    args = {
        'error_msg': error_msg,
        'phone_tool_page': True,
        'staff_page': True,
        'user': request.user,
        'request': request
    }
    return error_class(render_to_string('vr_dashboard/error.html', args))


def get_bogus_arg_error(request):
    return get_phone_tool_error(HttpResponseBadRequest,
                                request,
                                _('This request is not intended to be called directly.'))


def get_non_staff_phone_error(request, phone_number):
    return get_phone_tool_error(HttpResponseNotFound,
                                request,
                                _("Phone number %s is not a valid staff phone.") % phone_number)


def get_invalid_center_error(request, center_id):
    return get_phone_tool_error(HttpResponseNotFound,
                                request,
                                get_invalid_center_error_string(center_id))


def get_no_matching_phones_error(request):
    return get_phone_tool_error(HttpResponseNotFound,
                                request,
                                _('No matching phones were found.'))


@user_passes_test(lambda user: user.is_staff)
def matching_phones(request):
    center_id = request.GET.get('center_id')
    if not center_id or not is_center_id_valid(center_id):
        return get_bogus_arg_error(request)  # user bypassed form validation

    matches = StaffPhone.objects.filter(registration_center__center_id=center_id)
    if not matches.exists():
        if not RegistrationCenter.objects.filter(center_id=center_id).exists():
            return get_invalid_center_error(request, center_id)
        else:
            return get_no_matching_phones_error(request)

    for phone in matches:
        try:
            phone.whitelist = Whitelist.objects.get(phone_number=phone.phone_number)
        except Whitelist.DoesNotExist:
            pass

    return render(request, 'vr_dashboard/phone_tool/phone_list.html', {
        'phone_tool_page': True,
        'staff_page': True,
        'phones': matches,
        'center_id': center_id,
    })


@user_passes_test(lambda user: user.is_staff)
def phone_history(request):
    if 'phone' not in request.GET:
        return get_bogus_arg_error(request)

    phone_number = request.GET['phone']
    if not is_valid_phone_number(phone_number):
        return get_bogus_arg_error(request)  # user bypassed form validation

    try:
        staff_phone = StaffPhone.objects.get(phone_number=phone_number)
    except StaffPhone.DoesNotExist:
        # This feature is only for staff phones, but we need to be able to
        # find messages from would-be staff phones that haven't been
        # successfully linked.
        staff_phone = None

    try:
        whitelist = Whitelist.objects.get(phone_number=phone_number)
    except Whitelist.DoesNotExist:
        whitelist = None

    either_number = Q(from_number=phone_number) | Q(to_number=phone_number)
    sms_messages = SMS.objects.filter(either_number).order_by('-creation_date')
    for message in sms_messages:
        message.msg_type_string = MESSAGE_TYPES.get(message.msg_type, message.msg_type)

    return render(request, 'vr_dashboard/phone_tool/message_list.html', {
        'phone_tool_page': True,
        'staff_page': True,
        'sms_messages': sms_messages,
        'whitelist': whitelist,
        'phone': staff_phone,
        'phone_number': phone_number  # whether or not it is a staff phone
    })


@user_passes_test(lambda user: user.is_staff)
def whitelist_phone(request):
    phone_number = request.POST.get('phone')
    if not phone_number or not is_valid_phone_number(phone_number):
        return get_bogus_arg_error(request)  # user bypassed form validation

    center_id = request.POST.get('center_id')
    if center_id:
        if not is_center_id_valid(center_id):
            return get_bogus_arg_error(request)  # user bypassed form validation

    white_list = Whitelist(creation_date=now(), modification_date=now(), phone_number=phone_number)
    white_list.full_clean()
    white_list.save()

    # refresh the page that sent us here, now with the phone white-listed
    if center_id:
        query_args = '?center_id=%s' % center_id
        return HttpResponseRedirect(reverse('vr_dashboard:search-phones') + query_args)
    else:
        query_args = '?phone=%s' % phone_number
        return HttpResponseRedirect(reverse('vr_dashboard:phone-history') + query_args)
