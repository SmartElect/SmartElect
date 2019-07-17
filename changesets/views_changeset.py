# Python
from http.client import TEMPORARY_REDIRECT, BAD_REQUEST, FORBIDDEN

# 3rd party
from bread.bread import Bread, EditView, AddView, DeleteView, ReadView
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.views.generic import DetailView
from django_filters import FilterSet

# Project
from libya_elections.filters import LibyaChoiceFilter
from .forms import ChangesetForm
from libya_elections.libya_bread import StaffBreadMixin, PaginatedBrowseView
from .models import Changeset
from libya_elections.utils import get_comma_delimiter


class ChangesetFilterset(FilterSet):
    """FilterSet for browsing changesets."""
    change = LibyaChoiceFilter(choices=Changeset.CHANGE_CHOICES)
    status = LibyaChoiceFilter(choices=Changeset.STATUS_CHOICES)

    class Meta:
        model = Changeset
        fields = ['status', 'change']


class ChangesetBrowse(PaginatedBrowseView):
    columns = [
        (_('Created'), 'formatted_creation_date', 'creation_date'),
        (_('Name'), 'name'),
        (_('Status'), 'get_status_display'),
        (_('Approvals'), 'number_of_approvals'),
    ]
    filterset = ChangesetFilterset
    search_fields = ['name', 'message', 'justification']
    search_terms = _('name, message, or justification')

    def get_queryset(self):
        return super(ChangesetBrowse, self).get_queryset().order_by('-creation_date')


def display_selected_centers(changeset):
    if changeset.how_to_select == changeset.SELECT_CENTERS:
        centers = [str(center) for center in changeset.selected_centers.order_by('center_id')]
        return get_comma_delimiter().join(centers)


def display_target_center(changeset):
    if changeset.change == changeset.CHANGE_CENTER:
        return changeset.target_center


def display_how_to_select(changeset):
    if changeset.user_chooses_select_method:
        return changeset.get_how_to_select_display()


def display_number_of_uploaded_voters(changeset):
    if changeset.how_to_select == changeset.SELECT_UPLOADED_NIDS:
        return changeset.selected_citizens.count()


def display_approvers(changeset):
    if changeset.number_of_approvals:
        return get_comma_delimiter().join([str(user) for user in changeset.approvers.all()])


def display_error_text(changeset):
    if changeset.has_been_executed() and changeset.error_text:
        return changeset.error_text


def paragraphs(text):
    if text:
        parts = text.split('\n')
        parts = [conditional_escape(part) for part in parts]
        return mark_safe('<br>'.join(parts))


class ChangesetRead(ReadView):
    form_class = ChangesetForm

    def get_form(self, data=None, files=None, **kwargs):
        kwargs.setdefault('request', self.request)
        return ChangesetForm(data=data, files=files, **kwargs)

    def get_read_rows(self):
        """
        Returns an iterable of (field, value, link) that can be passed
        to the template.

        field is a django db field instance.  Use field.verbose_name to
        get the label and field.help_text to get the help, if any.

        If value is None, the entire row will be skipped (not displayed)
        in the template.

        If there's a link, it'll be rendered something like

          <label><a href="{{ link }}">{{ label|capfirst }}</a></label>
          <div class="read-value"><a href="{{ link }}">{{ value }}</a></div>

        and otherwise

          <label>{{ label|capfirst }}</label>
          <div class="read-value">{{ value }}</div>

        where 'label' is field.verbose_name.
        """
        changeset = self.object
        uploaded_url = (reverse('browse_uploadedcitizens') + '?changeset=%d' % changeset.pk)
        if changeset.has_been_executed():
            affected_url = reverse('browse_changerecords') + '?changeset=%d' % changeset.pk
        else:
            affected_url = None
        # Start with just the field name in the first place. Or if there's no field,
        # put None in the first place and add on the desired label and help text
        # at the end.  Then we'll fix it up.
        rows = [
            ('name', changeset.name, None),
            ('status', changeset.get_status_display(), None),
            ('change', changeset.get_change_display(), None),
            ('target_center', display_target_center(changeset), None),
            ('how_to_select', display_how_to_select(changeset), None),
            ('selected_centers', display_selected_centers(changeset), None),

            (None, display_number_of_uploaded_voters(changeset), uploaded_url,
             _('Number of uploaded voters')),

            (None, changeset.number_affected(), affected_url, _('Number of affected voters')),

            ('other_changeset', changeset.other_changeset, None),
            ('creation_date', changeset.formatted_creation_date),
            ('created_by', changeset.created_by),
            ('message', changeset.message),
            ('justification', paragraphs(changeset.justification)),

            (None, changeset.number_of_approvals, None, _("Number of approvals")),

            ('approvers', display_approvers(changeset)),
            ('execution_start_time', changeset.execution_start_time),
            ('queued_by', changeset.queued_by),
            ('finish_time', changeset.finish_time),
            ('rollback_changeset', changeset.rollback_changeset),
            ('error_text', paragraphs(display_error_text(changeset))),
        ]

        # Now change the first item in each entry to the actual field object
        def fix_field(row):
            # Row is a tuple, return a new tuple
            row = list(row)
            if row[0] is None:
                # No field, make a fake one to pass to the template
                while len(row) < 5:
                    row.append(None)

                class DummyField:
                    verbose_name = row[3]
                    help_text = row[4]
                row[0] = DummyField()
            else:
                row[0] = Changeset._meta.get_field(row[0])
            # Return a tuple, with any extra fields for label, help thrown away now
            return tuple(row[:3])

        rows = [fix_field(row) for row in rows]
        return rows

    def get_context_data(self, **kwargs):
        context = super(ChangesetRead, self).get_context_data(**kwargs)
        context['read_rows'] = self.get_read_rows()
        changeset = self.get_object()
        context['editable'] = (changeset.in_editable_status()
                               and changeset.may_be_edited_by(self.request.user))
        context['approvable'] = (changeset.in_approvable_status()
                                 and changeset.may_be_approved_by(self.request.user))
        # Lots of context needed to control what we display on the page
        context['number_needed'] = settings.MINIMUM_CHANGESET_APPROVALS
        context['may_approve'] = (changeset.may_be_approved_by(self.request.user)
                                  and not changeset.has_been_queued())
        context['has_approved'] = changeset.is_approved_by(self.request.user)
        context['can_queue'] = (changeset.in_queueable_status()
                                and changeset.may_be_queued_by(self.request.user))
        return context


class ChangesetEdit(EditView):
    form_class = ChangesetForm

    def dispatch(self, request, *args, **kwargs):
        changeset = self.get_object()
        if not changeset.in_editable_status():
            messages.info(request, _("Changeset can no longer be edited"))
            return redirect('read_changeset', pk=changeset.pk)
        return super(ChangesetEdit, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ChangesetEdit, self).get_context_data(**kwargs)
        context['changeset'] = context['form'].instance
        return context

    def get_form(self, data=None, files=None, **kwargs):
        kwargs.setdefault('request', self.request)
        return ChangesetForm(data=data, files=files, **kwargs)


class ChangesetAdd(AddView):
    form_class = ChangesetForm

    def get_context_data(self, **kwargs):
        context = super(ChangesetAdd, self).get_context_data(**kwargs)
        context['changeset'] = context['form'].instance
        return context

    def get_form(self, data=None, files=None, **kwargs):
        kwargs.setdefault('request', self.request)
        return ChangesetForm(data=data, files=files, **kwargs)


class ChangesetDelete(DeleteView):

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(),
                                     settings.LOGIN_URL,
                                     REDIRECT_FIELD_NAME)
        object = self.get_object()
        if not object.may_be_deleted_by(request.user):
            raise PermissionDenied
        if not object.in_deletable_status():
            messages.error(request, _("This changeset may no longer be deleted."))
            return redirect(reverse('read_changeset', args=[object.pk]))
        return super(ChangesetDelete, self).dispatch(request, *args, **kwargs)


class ChangesetBread(StaffBreadMixin, Bread):
    add_view = ChangesetAdd
    browse_view = ChangesetBrowse
    delete_view = ChangesetDelete
    edit_view = ChangesetEdit
    model = Changeset
    read_view = ChangesetRead


class ApproveView(DetailView):
    """
    If the user has permission, allows them
    to update approvals, and possibly even start the change.
    """
    http_method_names = ['post']
    model = Changeset
    template_name = 'changesets/changeset_read.html'

    def dispatch(self, request, *args, **kwargs):
        # User has to be logged in
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(),
                                     settings.LOGIN_URL,
                                     REDIRECT_FIELD_NAME)
        return super(ApproveView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        kwargs = super(ApproveView, self).get_context_data(**kwargs)
        kwargs['staff_page'] = True
        kwargs['bread'] = {
            'browse_url_name': 'browse_changesets',
            'edit_url_name': 'edit_changeset',
            'delete_url_name': 'delete_changeset',
        }
        return kwargs

    def post(self, request, *args, **kwargs):
        """
        User wants to approve, revoke, start, etc.
        """
        changeset = self.object = self.get_object()
        user = self.request.user
        # By default we'll redirect to the read view, but we'll
        # change this if we want to return another page.
        status = TEMPORARY_REDIRECT
        redirect_url = reverse('read_changeset', args=[changeset.pk])

        if changeset.has_been_queued():
            # Too late
            messages.error(request, _("You cannot do that after the changeset has been started."))
            status = BAD_REQUEST
        elif 'approve' in request.POST:
            if changeset.is_approved_by(user):
                messages.error(request, _("You have already approved this changeset."))
            elif changeset.may_be_approved_by(user):
                changeset.approve(request.user)
                messages.info(request, _("You have approved this changeset."))
            else:
                messages.error(request, _("You are not authorized to approve this changeset."))
                status = FORBIDDEN
        elif 'revoke' in request.POST:
            if changeset.is_approved_by(user):
                changeset.revoke_approval(request.user)
                messages.info(request, _("You have revoked your approval."))
            else:
                messages.error(request, _("You did not approve this changeset."))
                status = BAD_REQUEST
        elif 'queue' in request.POST:
            if changeset.may_be_queued_by(user):
                if not changeset.in_queueable_status():
                    messages.error(request,
                                   _("Changesets can only be started when they are in "
                                     "the approved status."))
                    status = BAD_REQUEST
                else:
                    changeset.queued_by = user
                    changeset.save()
                    changeset.queue()
                    redirect_url = reverse('read_changeset', kwargs=dict(pk=changeset.pk))
                    messages.info(request, "Changeset has been submitted for processing.")
            else:
                messages.error(request, _("You are not authorized to start this changeset."))
                status = FORBIDDEN
        else:
            status = BAD_REQUEST

        if status == TEMPORARY_REDIRECT:
            return redirect(redirect_url)
        else:
            return self.render_to_response(
                self.get_context_data(),
                status=status,
            )
