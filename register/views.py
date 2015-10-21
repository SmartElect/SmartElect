# Python imports
from __future__ import unicode_literals
from __future__ import division
import datetime

# Django imports
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import permission_required, login_required
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse_lazy
from django.db.models.loading import get_model
from django import forms
from django.http import HttpResponse, HttpResponseNotFound
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import ugettext_lazy as _

# 3rd party imports
from braces.views import StaffuserRequiredMixin
from bread.bread import EditView as BreadEditView, LabelValueReadView as BreadLabelValueReadView
from django_filters import Filter, FilterSet
from vanilla import FormView

# This project's imports
from .forms import CSV_FIELDS, UploadCenterForm, BlackWhiteListedNumbersUploadForm, \
    BlacklistedNumberEditForm, WhitelistedNumberEditForm, RegistrationCenterEditForm
from .models import Blacklist, Whitelist, Registration, RegistrationCenter, Office, Constituency, \
    SubConstituency, SMS
from .utils import process_blackwhitelisted_numbers_file
from civil_registry.models import Citizen
from libya_elections.csv_utils import UnicodeWriter
from libya_elections.filters import LibyaChoiceFilter
from libya_elections.libya_bread import PaginatedBrowseView, SoftDeleteBread, SoftDeleteDeleteView, \
    StaffBreadMixin
from libya_elections.utils import LoginPermissionRequiredMixin, get_verbose_name, format_tristate, \
    get_comma_delimiter
from polling_reports.models import StaffPhone
from staff.views import StaffViewMixin
from text_messages.models import MessageText


def prepare_loadtest(request):  # pragma: no cover
    # Only run if this server is meant to run load tests
    if not settings.LOAD_TEST:
        return HttpResponseNotFound()

    # Delete Registrations, Citizens and Centers
    Citizen.objects.all().delete()
    Registration.objects.unfiltered().delete()
    RegistrationCenter.objects.all().delete()

    # create valid persons
    first_national_id = 100000000000
    birth_date = datetime.date(1913, 2, 3)
    citizens = []
    default_count = 20000
    count = request.GET.get('n', default_count)
    try:
        count = int(count)
    except ValueError:
        count = default_count
    if count < 0:
        count = default_count
    for i in range(count):
        citizens.append(Citizen(national_id=first_national_id + i,
                                birth_date=birth_date))
    Citizen.objects.bulk_create(citizens)

    # create 1000 valid centers
    # we don't need more than 1000, b/c they can be reused over and over
    first_center_id = 10000
    centers = []
    for i in range(1000):
        centers.append(RegistrationCenter(center_id=first_center_id + i))
    RegistrationCenter.objects.bulk_create(centers)

    return HttpResponse("Load test data created (n=%s)." % count)


@login_required
@permission_required('register.delete_registrationcenter', raise_exception=True)
def delete_all_copy_centers(request):
    """View to handle GET & POST of 'confirm delete all copy centers' form"""
    centers = RegistrationCenter.objects.filter(copy_of__isnull=False)

    if request.method == 'POST':
        if 'ok' in request.POST:
            RegistrationCenter.objects.delete_all_copy_centers()
            messages.success(request, _('All copy centres have been deleted.'))

        return redirect('browse_registrationcenters')
    else:
        center_names = ["{} - {}".format(center.center_id, center.name) for center in centers]
        center_names = ', '.join(center_names)

        context = {'copy_centers': centers,
                   'center_names': center_names,
                   'staff_page': True,
                   }

        return render(request, 'register/delete_all_copy_centers.html', context)


def format_field(center, field):
    """
    Given a registration center and a field name, return the value
    of the field formatted to export in a CSV file.
    """
    if field == 'center_type':
        return unicode(center.get_center_type_display())
    # We never want to print "None", but "0" is okay.
    val = getattr(center, field, None)
    if val is None:
        val = ''
    return unicode(val)


def prepare_csv_response(filename_prefix):
    # Proper MIME type is text/csv. ref: http://tools.ietf.org/html/rfc4180
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = "{}-{}.csv".format(filename_prefix, datetime.date.today().isoformat())
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
    return response


@login_required
@permission_required('register.read_registrationcenter', raise_exception=True)
def download_centers_csv(request):
    """View to handle 'download centers as CSV' link"""
    response = prepare_csv_response('centers')
    writer = UnicodeWriter(response)
    # write header row
    writer.writerow(CSV_FIELDS)
    for center in RegistrationCenter.objects.all():
        writer.writerow([format_field(center, field) for field in CSV_FIELDS])
    return response


class AllNamedThingsFilter(LibyaChoiceFilter):
    """A semi-generic filter that displays NamedThings in a select listbox.

    The model of the thing on which you want to filter must be passed as the 'filter_by_model'
    kwarg in the constructor. It can be a direct reference to the model or a string like
    'register.Office'.

    This only works for objects descended from the NamedThing model because it makes assumptions
    about the instances' attributes.
    """
    def __init__(self, *args, **kwargs):
        if 'filter_by_model' not in kwargs:
            raise ValueError("filter_by_model must be passed in kwargs")
        filter_by_model = kwargs.pop('filter_by_model')
        if isinstance(filter_by_model, basestring):
            filter_by_model = get_model(filter_by_model)

        self.filter_by_model = filter_by_model
        self._choices = None

        super(AllNamedThingsFilter, self).__init__(*args, **kwargs)

    @property
    def field(self):
        if self._choices is None:
            # Cache choices
            self._choices = [(thing.id, '{} - {}'.format(thing.id, thing.name)) for thing in
                             self.filter_by_model.objects.all()]

        self.extra['choices'] = self._choices
        return super(AllNamedThingsFilter, self).field


class UploadCenterView(LoginPermissionRequiredMixin, StaffuserRequiredMixin, StaffViewMixin,
                       FormView):
    """View to handle 'upload centers via CSV' link"""
    form_class = UploadCenterForm
    permission_required = "register.add_registrationcenter"
    raise_exception = True
    success_url = reverse_lazy('upload-centers-csv')
    template_name = 'register/upload_centers_csv.html'

    def get_context_data(self, **kwargs):
        context = super(UploadCenterView, self).get_context_data(**kwargs)
        context['csv_columns'] = ', '.join(CSV_FIELDS)
        return context

    def form_valid(self, form):
        msg, status = form.process()
        if status:
            messages.success(self.request, msg)
        else:
            messages.error(self.request, msg)
        return super(UploadCenterView, self).form_valid(form)


class BlacklistedNumberBrowse(PaginatedBrowseView):
    columns = [
        (get_verbose_name(Blacklist, 'phone_number'), 'formatted_phone_number_tag', 'phone_number'),
        (get_verbose_name(Blacklist, 'creation_date'), 'formatted_creation_date',
         'creation_date'),
        (get_verbose_name(Blacklist, 'modification_date'), 'formatted_modification_date',
         'modification_date'),
    ]
    search_fields = ('phone_number', )
    search_terms = _('Phone Number')


class BlacklistedNumberRead(BreadLabelValueReadView):
    fields = ((get_verbose_name(Blacklist, 'phone_number'), 'formatted_phone_number_tag'),
              (get_verbose_name(Blacklist, 'creation_date'), 'formatted_creation_date'),
              (get_verbose_name(Blacklist, 'modification_date'), 'formatted_modification_date'),
              )


class BlacklistedNumberBread(StaffBreadMixin, SoftDeleteBread):
    model = Blacklist
    name = 'blacklistednumber'
    plural_name = 'blacklistednumbers'
    browse_view = BlacklistedNumberBrowse
    read_view = BlacklistedNumberRead
    form_class = BlacklistedNumberEditForm


class WhitelistedNumberBrowse(PaginatedBrowseView):
    columns = [
        (get_verbose_name(Whitelist, 'phone_number'), 'formatted_phone_number_tag', 'phone_number'),
        (get_verbose_name(Whitelist, 'creation_date'), 'formatted_creation_date',
         'creation_date'),
        (get_verbose_name(Whitelist, 'modification_date'), 'formatted_modification_date',
         'modification_date'),
    ]
    search_fields = ('phone_number', )
    search_terms = _('Phone Number')


class WhiteListedNumberRead(BreadLabelValueReadView):
    fields = ((get_verbose_name(Whitelist, 'phone_number'), 'formatted_phone_number_tag'),
              (get_verbose_name(Whitelist, 'creation_date'), 'formatted_creation_date'),
              (get_verbose_name(Whitelist, 'modification_date'), 'formatted_modification_date'),
              )


class WhitelistedNumberBread(StaffBreadMixin, SoftDeleteBread):
    model = Whitelist
    name = 'whitelistednumber'
    plural_name = 'whitelistednumbers'
    browse_view = WhitelistedNumberBrowse
    read_view = WhiteListedNumberRead
    form_class = WhitelistedNumberEditForm


@login_required
@permission_required('register.read_whitelist', raise_exception=True)
def download_whitelisted_numbers(request):
    """View to handle 'download whitelisted numbers' link"""
    return download_blackwhitelisted_numbers('white')


@login_required
@permission_required('register.read_blacklist', raise_exception=True)
def download_blacklisted_numbers(request):
    """View to handle 'download blacklisted numbers' link"""
    return download_blackwhitelisted_numbers('black')


def download_blackwhitelisted_numbers(list_type):
    """Common handler for black- & whitelisted number download.

    Permissions must be tested by the calling view; they're not checked here.
    """
    # Technically this is not a CSV since there's only one column, but treating it as
    # a CSV will make it easier to use with Excel, etc.

    response = prepare_csv_response('{}list'.format(list_type))
    writer = UnicodeWriter(response)
    model = Blacklist if list_type == 'black' else Whitelist
    for number in model.objects.all():
        writer.writerow([number.phone_number])
    return response


@login_required
@permission_required('register.add_blacklist', raise_exception=True)
def upload_blacklisted_numbers(request):
    """View handler for uploading a list of blacklisted numbers."""
    return upload_blackwhitelisted_numbers(request, 'black')


@login_required
@permission_required('register.add_whitelist', raise_exception=True)
def upload_whitelisted_numbers(request):
    """View handler for uploading a list of whitelisted numbers."""
    return upload_blackwhitelisted_numbers(request, 'white')


def upload_blackwhitelisted_numbers(request, list_type):
    """Common handler for black- & whitelisted number upload.

    Permissions must be tested by the calling view; they're not checked here.
    """
    context = {
        'list_type': list_type,
        'staff_page': True,
    }
    model = Blacklist if list_type == 'black' else Whitelist
    if request.method == 'POST':
        form = BlackWhiteListedNumbersUploadForm(request.POST, request.FILES)
        if form.is_valid():
            import_file = request.FILES['import_file']
            imported, skipped, errors = process_blackwhitelisted_numbers_file(model, import_file)
            messages.success(request, "%d numbers added. %d numbers already present in %slist." %
                             (imported, skipped, list_type))
            if errors:
                messages.error(request,
                               _("Numbers on these lines not imported because they are "
                                 "not valid phone numbers: %s.") % ', '.join(errors))

            return redirect('browse_{}listednumbers'.format(list_type))
    else:
        form = BlackWhiteListedNumbersUploadForm()
    context['form'] = form

    return render(request, 'register/upload_blackwhitelisted_numbers.html', context)


@login_required
@permission_required('register.delete_blacklist', raise_exception=True)
def delete_all_blacklisted_numbers(request):
    """View to handle GET & POST of 'confirm delete all blacklisted numbers'"""
    return delete_blackwhitelisted_numbers(request, 'black')


@login_required
@permission_required('register.delete_whitelist', raise_exception=True)
def delete_all_whitelisted_numbers(request):
    """View to handle GET & POST of 'confirm delete all whitelisted numbers'"""
    return delete_blackwhitelisted_numbers(request, 'white')


def delete_blackwhitelisted_numbers(request, list_type):
    """Common handler for black- & whitelisted number deletion.

    Permissions must be tested by the calling view; they're not checked here.
    """
    model = Blacklist if list_type == 'black' else Whitelist
    if request.method == 'POST':
        if 'ok' in request.POST:
            model.objects.all().update(deleted=True)
            message = 'All {}listed numbers have been deleted.'.format(list_type)
            messages.success(request, _(message))
        url = 'browse_{}listednumbers'.format(list_type)
        return redirect(url)
    else:
        context = {
            'list_type': list_type,
            'object_count': model.objects.count(),
            'staff_page': True,
        }
        return render(request, 'register/delete_all_blackwhitelisted_numbers.html', context)


@login_required
@permission_required('polling_reports.delete_staffphone', raise_exception=True)
def delete_all_staff_phones(request):
    """View to handle GET & POST of 'confirm delete all staff phones'"""
    if request.method == 'POST':
        if 'ok' in request.POST:
            StaffPhone.objects.all().update(deleted=True)
            messages.success(request, _("All Staff Phones have been deleted."))
        return redirect('browse_staffphones')
    else:
        context = {
            'object_count': StaffPhone.objects.count(),
            'staff_page': True,
        }
        return render(request, 'polling_reports/delete_all_staffphones.html', context)


class StaffPhoneFilterset(FilterSet):
    """FilterSet for browsing staff phones."""
    registration_center__office = AllNamedThingsFilter(filter_by_model=Office)
    registration_center__subconstituency = AllNamedThingsFilter(filter_by_model=SubConstituency)

    class Meta:
        model = StaffPhone
        fields = ['registration_center__office', 'registration_center__subconstituency', ]

    def __init__(self, *args, **kwargs):
        super(StaffPhoneFilterset, self).__init__(*args, **kwargs)
        self.filters['registration_center__office'].label = \
            get_verbose_name(RegistrationCenter, 'office')
        self.filters['registration_center__subconstituency'].label = \
            get_verbose_name(RegistrationCenter, 'subconstituency')


class StaffPhoneBrowse(PaginatedBrowseView):
    columns = [
        (_('creation date'), 'formatted_creation_date', 'creation_date'),
        (_('Phone number'), 'formatted_phone_number_tag'),
        (_('Registration center'), 'registration_center'),
    ]
    filterset = StaffPhoneFilterset
    search_fields = ['registration_center__center_id', 'registration_center__name', 'phone_number']
    search_terms = _('Center Id, Center name, or Phone number')


class StaffPhoneReadView(BreadLabelValueReadView):
    fields = (
        (get_verbose_name(StaffPhone, 'phone_number'), 'formatted_phone_number_tag'),
        (get_verbose_name(StaffPhone, 'registration_center'), 'registration_center_as_html'),
        (get_verbose_name(StaffPhone, 'creation_date'), 'formatted_creation_date'),
        (get_verbose_name(StaffPhone, 'modification_date'), 'formatted_modification_date'),
    )


class StaffPhoneBread(StaffBreadMixin, SoftDeleteBread):
    model = StaffPhone
    browse_view = StaffPhoneBrowse
    read_view = StaffPhoneReadView


class SMSReadView(BreadLabelValueReadView):
    """View for reading SMSes."""
    fields = ((get_verbose_name(SMS, 'from_number'), 'from_number_formatted_tag'),
              (get_verbose_name(SMS, 'to_number'), 'to_number_formatted_tag'),
              (get_verbose_name(SMS, 'citizen'), 'citizen_as_html'),
              (None, 'carrier'),
              (get_verbose_name(SMS, 'direction'), 'direction_formatted'),
              (get_verbose_name(SMS, 'msg_type'), 'msg_type_formatted'),
              (None, 'message'),
              (get_verbose_name(SMS, 'message_code'), 'get_message_code_display'),
              (None, 'uuid'),
              (None, 'is_audited'),
              (get_verbose_name(SMS, 'in_response_to'), 'in_response_to_as_html'),
              (None, 'need_to_anonymize'),
              (get_verbose_name(SMS, 'creation_date'), 'formatted_creation_date'),
              (get_verbose_name(SMS, 'modification_date'), 'formatted_modification_date'),
              )


class SMSFilterSet(FilterSet):
    direction = LibyaChoiceFilter(choices=SMS.DIRECTION_CHOICES)
    msg_type = LibyaChoiceFilter(label=_('Message Type'),
                                 choices=SMS.MESSAGE_TYPES)
    message_code = LibyaChoiceFilter(label=_('Message Code'))

    class Meta:
        model = SMS
        fields = ['direction', 'msg_type', 'message_code']

    def __init__(self, *args, **kwargs):
        super(SMSFilterSet, self).__init__(*args, **kwargs)
        MESSAGE_CODE_LABELS = [
            (msg.number, msg.label) for msg in MessageText.objects.all()
        ]
        self.filters['message_code'].extra['choices'] = MESSAGE_CODE_LABELS


class SMSBrowse(PaginatedBrowseView):
    filterset = SMSFilterSet
    columns = [
        (get_verbose_name(SMS, 'creation_date'), 'formatted_creation_date', 'creation_date'),
        (get_verbose_name(SMS, 'from_number'), 'from_number_formatted_tag', 'from_number'),
        (get_verbose_name(SMS, 'direction'), 'get_direction_display', 'direction'),
        (get_verbose_name(SMS, 'to_number'), 'to_number_formatted_tag', 'to_number'),
        (get_verbose_name(SMS, 'message_code'), 'get_message_code_display', 'message_code'),
        (get_verbose_name(SMS, 'message'), 'message'),
    ]

    def get_queryset(self, *args, **kwargs):
        queryset = super(SMSBrowse, self).get_queryset(*args, **kwargs)

        if not queryset.ordered:
            queryset = queryset.order_by('-creation_date')
        # else:
            # The queryset is already ordered according to the user's preference.

        return queryset


class SMSBread(StaffBreadMixin, SoftDeleteBread):
    model = SMS
    browse_view = SMSBrowse
    read_view = SMSReadView
    plural_name = 'messages'
    views = 'BR'


class RegistrationCenterFilterset(FilterSet):
    """FilterSet for browsing registration centers."""
    center_type = LibyaChoiceFilter(choices=RegistrationCenter.Types.CHOICES)
    office = AllNamedThingsFilter(filter_by_model=Office)
    constituency = AllNamedThingsFilter(filter_by_model=Constituency)
    subconstituency = AllNamedThingsFilter(filter_by_model=SubConstituency)

    class Meta:
        model = RegistrationCenter
        fields = ['center_type', 'office', 'constituency', 'subconstituency', ]


class RegistrationCenterBrowseView(PaginatedBrowseView):
    """View for browsing centers."""
    columns = [
        (_('Center Id'), 'center_id'),
        (_('Name'), 'name'),
        # This sorts by the internal number representing the type, which is the
        # best we can do via the database since we don't actually store the center
        # type names in the database.
        (_('Type'), 'center_type_label', 'center_type'),
        # Sort these columns by the name in the language that is current at the time
        # we process the view
        (_('Office'), 'office__name', lambda: 'office__' + Office.get_name_field_name()),
        (_('Constituency'), 'constituency__name',
         lambda: 'constituency__' + Constituency.get_name_field_name()),
        (_('Subconstituency'), 'subconstituency__name',
         lambda: 'subconstituency__' + SubConstituency.get_name_field_name()),
        (_('Supports Registrations'), 'reg_open'),
    ]
    filterset = RegistrationCenterFilterset
    search_fields = ['center_id', 'name']
    search_terms = _('Center Id, Center name')


def get_copied_by_formatted(context):
    """Return a list of them centers that are copies of the one referenced in the context.

    The list is nicely formatted for display. Context should be a view context with
    context['object'] referring to the copied center.

    This is a support function for RegistrationCenterReadView.
    """
    original = context['object']

    copies = get_comma_delimiter().join(['{} - {}'.format(copy_center.center_id, copy_center.name)
                                        for copy_center in original.copied_by.all()])

    return copies or _("No copies")


class RegistrationCenterConditionalDeleteMixin(object):
    """Mixin for read and edit views; implements special may_delete logic"""
    def get_context_data(self, **kwargs):
        context = super(RegistrationCenterConditionalDeleteMixin, self).get_context_data(**kwargs)
        # Regardless of the user's permissions, centers with copies may not be deleted.
        context['may_delete'] = context['may_delete'] and (not context['object'].has_copy)
        return context


class RegistrationCenterReadView(RegistrationCenterConditionalDeleteMixin, BreadLabelValueReadView):
    """View for reg center read, implements special delete logic via mixin"""
    fields = [
        (None, 'center_id'),
        (None, 'name'),
        (get_verbose_name(RegistrationCenter, 'office'), 'office_as_html'),
        (get_verbose_name(RegistrationCenter, 'constituency'), 'constituency_as_html'),
        (get_verbose_name(RegistrationCenter, 'subconstituency'), 'subconstituency_as_html'),
        (None, 'mahalla_name'),
        (None, 'village_name'),
        (get_verbose_name(RegistrationCenter, 'center_type'), 'center_type_label'),
        (None, 'center_lat'),
        (None, 'center_lon'),
        (None, 'copy_of'),
        (_("Copied by"), get_copied_by_formatted),
        (get_verbose_name(RegistrationCenter, 'reg_open'),
         lambda context: format_tristate(context['object'].reg_open)),
        (get_verbose_name(RegistrationCenter, 'creation_date'), 'formatted_creation_date'),
        (get_verbose_name(RegistrationCenter, 'modification_date'), 'formatted_modification_date'),
    ]


class RegistrationCenterEditView(RegistrationCenterConditionalDeleteMixin, BreadEditView):
    """View for reg center edit, implements special delete logic via mixin"""
    pass


class RegistrationCenterDeleteView(SoftDeleteDeleteView):
    """Registration center delete view to implement a custom delete rule"""
    def dispatch(self, request, *args, **kwargs):
        response = super(RegistrationCenterDeleteView, self).dispatch(request, *args, **kwargs)

        if response.status_code == 200:
            # Before returning the delete page, make one final check.
            center = get_object_or_404(RegistrationCenter, pk=kwargs['pk'])

            if center.has_copy:
                # Centers with copies can't be deleted.
                raise PermissionDenied

        return response


class RegistrationCenterBread(StaffBreadMixin, SoftDeleteBread):
    browse_view = RegistrationCenterBrowseView
    read_view = RegistrationCenterReadView
    edit_view = RegistrationCenterEditView
    delete_view = RegistrationCenterDeleteView
    model = RegistrationCenter
    form_class = RegistrationCenterEditForm


class OfficeBrowseView(PaginatedBrowseView):
    columns = [
        (_('Id'), 'id'),
        (_('Name (English)'), 'name_english'),
        (_('Name (Arabic)'), 'name_arabic'),
        # This sorts by the internal number representing the region, which is the
        # best we can do via the database since we don't actually store the region
        # names in the database.
        (_('Region'), 'region_name', 'region'),
    ]
    search_fields = ('id', 'name_english', 'name_arabic')
    search_terms = _('Id or Name (in English or Arabic)')


class OfficeReadView(BreadLabelValueReadView):
    """Semi-custom view for office read view"""
    fields = [
        (None, 'id'),
        (None, 'name_english'),
        (None, 'name_arabic'),
        (get_verbose_name(Office, 'region'), 'region_name'),
        (get_verbose_name(Office, 'creation_date'), 'formatted_creation_date'),
        (get_verbose_name(Office, 'modification_date'), 'formatted_modification_date'),
    ]


class OfficeBread(StaffBreadMixin, SoftDeleteBread):
    browse_view = OfficeBrowseView
    read_view = OfficeReadView
    model = Office


class ConstituencyBrowseView(PaginatedBrowseView):
    columns = [
        (_('Id'), 'id'),
        (_('Name (English)'), 'name_english'),
        (_('Name (Arabic)'), 'name_arabic'),
    ]
    search_fields = ('id', 'name_english', 'name_arabic')
    search_terms = _('Id or Name (in English or Arabic)')


class ConstituencyReadView(BreadLabelValueReadView):
    """Semi-custom view for constituency read view"""
    fields = [
        (None, 'id'),
        (None, 'name_english'),
        (None, 'name_arabic'),
        (get_verbose_name(Constituency, 'creation_date'), 'formatted_creation_date'),
        (get_verbose_name(Constituency, 'modification_date'), 'formatted_modification_date'),
    ]


class ConstituencyBread(StaffBreadMixin, SoftDeleteBread):
    browse_view = ConstituencyBrowseView
    read_view = ConstituencyReadView
    model = Constituency
    plural_name = 'constituencies'


class SubconstituencyBrowseView(PaginatedBrowseView):
    """View for browsing subconstituencies; uses custom template."""
    columns = [
        (_('Id'), 'id'),
        (_('Name (English)'), 'name_english'),
        (_('Name (Arabic)'), 'name_arabic'),
    ]
    search_fields = ('id', 'name_english', 'name_arabic')
    search_terms = _('Id or Name (in English or Arabic)')


class SubconstituencyReadView(BreadLabelValueReadView):
    """Semi-custom view for subcon read view"""
    fields = [
        (None, 'id'),
        (None, 'name_english'),
        (None, 'name_arabic'),
        (get_verbose_name(SubConstituency, 'creation_date'), 'formatted_creation_date'),
        (get_verbose_name(SubConstituency, 'modification_date'), 'formatted_modification_date'),
    ]


class SubconstituencyBread(StaffBreadMixin, SoftDeleteBread):
    browse_view = SubconstituencyBrowseView
    read_view = SubconstituencyReadView
    model = SubConstituency
    plural_name = 'subconstituencies'


class ArchiveTimeNotNoneFilter(Filter):
    field_class = forms.NullBooleanField

    def filter(self, qs, value):
        if value is True:
            return qs.exclude(archive_time=None)
        if value is False:
            return qs.filter(archive_time=None)
        return qs


class RegistrationFilterSet(FilterSet):

    archived = ArchiveTimeNotNoneFilter(
        widget=forms.widgets.Select(choices=(
            (None, _(u'Any')),
            (True, _(u'Yes')),
            (False, _(u'No'))
        ))
    )

    class Meta:
        model = Registration
        fields = ['registration_center', 'archived']


def get_registration_bread_queryset():
    # show archived but not deleted
    return Registration.objects.unfiltered().exclude(deleted=True)


class RegistrationBrowse(PaginatedBrowseView):
    filterset = RegistrationFilterSet
    queryset = get_registration_bread_queryset()
    columns = (
        (get_verbose_name(Citizen, 'national_id'), 'citizen__national_id'),
        (get_verbose_name(Registration, 'citizen'), 'citizen', False),
        (get_verbose_name(Registration, 'registration_center'), 'registration_center'),
        (get_verbose_name(Registration, 'archive_time'), 'formatted_archive_time'),
    )
    search_fields = ('citizen__national_id', 'citizen__first_name', 'citizen__father_name',
                     'citizen__grandfather_name', 'citizen__family_name')
    search_terms = _('national ID, first name, father name, grandfather name, family name ')

    def get_queryset(self, *args, **kwargs):
        queryset = super(RegistrationBrowse, self).get_queryset(*args, **kwargs)

        if not queryset.ordered:
            queryset = queryset.order_by('registration_center__center_id', '-modification_date')
        # else:
            # The queryset is already ordered according to the user's preference.

        # Fetch related entities in a single query rather than executing 1 query for each related
        # enitity for each registration.
        queryset = queryset.select_related('citizen', 'registration_center')

        return queryset


class RegistrationRead(BreadLabelValueReadView):
    queryset = get_registration_bread_queryset()
    fields = (
        (get_verbose_name(Registration, 'citizen'), 'citizen_as_html'),
        (get_verbose_name(Registration, 'registration_center'), 'registration_center_as_html'),
        (None, 'change_count'),
        (None, 'max_changes'),
        (None, 'repeat_count'),
        (_('Lock Status'), 'formatted_unlocked_until'),
        (get_verbose_name(Registration, 'sms'), 'sms_as_html'),
        (get_verbose_name(Registration, 'creation_date'), 'formatted_creation_date'),
        (get_verbose_name(Registration, 'modification_date'), 'formatted_modification_date'),
        (get_verbose_name(Registration, 'archive_time'), 'formatted_archive_time'),
    )


class RegistrationBread(StaffBreadMixin, SoftDeleteBread):
    model = Registration
    views = 'BR'
    browse_view = RegistrationBrowse
    read_view = RegistrationRead
