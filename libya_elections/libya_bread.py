from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.html import format_html, format_html_join
from django.utils.translation import ugettext_lazy as _

from bread.bread import BrowseView, DeleteView, Bread

from libya_elections.constants import ANCHOR_SNIPPET, LIBYA_DATE_FORMAT, LIBYA_DATETIME_FORMAT
from libya_elections.utils import get_comma_delimiter

# Paginator configuration:
# Show 2 pages at the beginning and end of range
NUM_PAGES_AT_HEAD_OR_TAIL = 2
# Show 1 page surrounding current page
NUM_PAGES_SURROUNDING_CURRENT = 1


class PaginatorMixin(object):
    """
    Mixin which can be added to Browse views to implement our custom pagination style.

    ASCII-art representation, viewing page 5 of 12:

      <1> <2> ... <4> 5 <6> ... <11> <12>

    The numbers 1, 2, 4, 6, 11, and 12 are linked. Page 5 is not. Other pages are elided.

    Provides `paginator_links` variable to the template.

    `paginator_links` is a list of 2-item lists [page_url, target]
    The inner lists have 3 possible formats:
      1) linked pages    : ['/blah/?page=4', 4]
      2) the current page: [None, 6]
      3) elided pages    : [None, None]

    It's up to the template to use those variables to format the paginator properly.
    """

    # Default paginate_by because BrowseView doesn't set one.
    # Classes using this can override.
    paginate_by = 20

    def get_context_data(self, **kwargs):
        data = super(PaginatorMixin, self).get_context_data(**kwargs)
        # get the paginator data structures
        paginator = data['paginator']
        page = data['page_obj']

        if data.get('is_paginated', False):
            # calculate ranges of pages we'll show (paginator list is 1-based)
            head_range = range(1, NUM_PAGES_AT_HEAD_OR_TAIL + 1)
            tail_range = range(paginator.num_pages - 1, paginator.num_pages + 1)
            surround_range = range(page.number - NUM_PAGES_SURROUNDING_CURRENT,
                                   page.number + NUM_PAGES_SURROUNDING_CURRENT + 1)
            paginator_ranges = head_range + tail_range + surround_range

            # Populate paginator_links
            paginator_links = []
            elided_flag = False
            for page_num in paginator.page_range:
                # surround_range includes page.number, so we test for page_number first
                if page_num == page.number:
                    paginator_links.append([None, page_num])
                    elided_flag = False
                elif page_num in paginator_ranges:
                    paginator_links.append([self._get_new_url(page=page_num), page_num])
                    elided_flag = False
                else:
                    if not elided_flag:
                        paginator_links.append([None, None])
                        elided_flag = True
                    # else:
                    #   we're already showing an ellipsis, so no need to add more
            data['paginator_links'] = paginator_links
        return data


class PaginatedBrowseView(PaginatorMixin, BrowseView):
    pass


class SoftDeleteDeleteView(DeleteView):
    """Delete view for models that use soft delete"""
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.soft_delete()
        return HttpResponseRedirect(self.get_success_url())


class SoftDeleteBread(Bread):
    delete_view = SoftDeleteDeleteView
    exclude = ['deleted']

# Mixins which provide suitable HTML for foreign key fields in Bread read views
# Some of these are already used in multiple models, others are not (yet).
# The standard behavior is to handle the lack of a linked field by returning
# NO_LINKED_OBJECT, although this feature is not required for all of these
# formatters.

NO_LINKED_OBJECT = _('None')


class BallotFormatterMixin(object):
    @property
    def ballot_as_html(self):
        """Return HTML for this instance's ballot field that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        if self.ballot is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET, self.ballot.get_absolute_url(),
                           unicode(self.ballot))


class BirthDateFormatterMixin(object):
    @property
    def formatted_birth_date(self):
        """Return this instance's birth_date field formatted as per Libyan standards."""
        return self.birth_date.strftime(LIBYA_DATE_FORMAT)


class CitizenFormatterMixin(object):
    @property
    def citizen_as_html(self):
        """Return HTML for this instance's citizen field that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        if self.citizen is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET, self.citizen.get_absolute_url(),
                           unicode(self.citizen))


class ConstituencyFormatterMixin(object):
    @property
    def constituency_as_html(self):
        """Return HTML for this instance's constituency field that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        if self.constituency is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET,
                           self.constituency.get_absolute_url(),
                           self.constituency_name)


class CreatedByFormatterMixin(object):
    @property
    def created_by_as_html(self):
        """Return HTML for this instance's created_by field (User) that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        if self.created_by is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET,
                           # User doesn't have a suitable get_absolute_url()
                           reverse('read_user', args=[self.created_by.id]),
                           unicode(self.created_by))


class ElectionFormatterMixin(object):
    @property
    def election_as_html(self):
        """Return HTML for this instance's election field that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        if self.election is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET, self.election.get_absolute_url(),
                           unicode(self.election))


class InResponseToFormatterMixin(object):
    @property
    def in_response_to_as_html(self):
        """Return HTML for this instance's in_response_to field (SMS) that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        if self.in_response_to is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET, self.in_response_to.get_absolute_url(),
                           unicode(self.in_response_to))


class OfficeFormatterMixin(object):
    @property
    def office_as_html(self):
        """Return HTML for this instance's office field that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        if self.office is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET, self.office.get_absolute_url(),
                           self.office_name)


class ElectionTimesFormatterMixin(object):
    @property
    def formatted_polling_start_time(self):
        """Return this instance's polling_start_time field formatted as per Libyan standards."""
        return self.polling_start_time.strftime(LIBYA_DATETIME_FORMAT)

    @property
    def formatted_polling_end_time(self):
        """Return this instance's polling_end_time field formatted as per Libyan standards."""
        return self.polling_end_time.strftime(LIBYA_DATETIME_FORMAT)

    @property
    def formatted_work_start_time(self):
        """Return this instance's work_start_time field formatted as per Libyan standards."""
        return self.work_start_time.strftime(LIBYA_DATETIME_FORMAT)

    @property
    def formatted_work_end_time(self):
        """Return this instance's work_end_time field formatted as per Libyan standards."""
        return self.work_end_time.strftime(LIBYA_DATETIME_FORMAT)


class RegistrationCenterFormatterMixin(object):
    @property
    def registration_center_as_html(self):
        """Return HTML for this instance's registration_center/center field that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        center = None
        found = False
        for attr_name in ('registration_center', 'center'):
            if hasattr(self, attr_name + '_id'):
                found = True
                try:
                    center = getattr(self, attr_name)
                except ObjectDoesNotExist:
                    center = None

        if not found:
            # Developer is confused
            raise AttributeError("Why are you using RegistrationCenterFormatterMixin on an object "
                                 "that doesn't have any registration center-related attributes?")
        if center is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET, center.get_absolute_url(), unicode(center))


class ReviewedByFormatterMixin(object):
    @property
    def reviewed_by_as_html(self):
        """Return HTML for this instance's reviewed_by field (User) that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        if self.reviewed_by is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET,
                           # User doesn't have a suitable get_absolute_url()
                           reverse('read_user', args=[self.reviewed_by.id]),
                           unicode(self.reviewed_by))


class SMSFormatterMixin(object):
    @property
    def sms_as_html(self):
        """Return HTML for this instance's sms field that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        if self.sms is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET, self.sms.get_absolute_url(),
                           unicode(self.sms))


class StartEndTimeFormatterMixin(object):
    @property
    def formatted_end_time(self):
        """Return this instance's end_time field formatted as per Libyan standards."""
        return self.end_time.strftime(LIBYA_DATETIME_FORMAT)

    @property
    def formatted_start_time(self):
        """Return this instance's start_time field formatted as per Libyan standards."""
        return self.start_time.strftime(LIBYA_DATETIME_FORMAT)


class SubconstituencyFormatterMixin(object):
    @property
    def subconstituency_as_html(self):
        """Return HTML for this instance's subconstituency field that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        if self.subconstituency is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET, self.subconstituency.get_absolute_url(),
                           self.subconstituency_name)


class SubconstituenciesFormatterMixin(object):
    @property
    def subconstituencies_as_html(self):
        """Return HTML for this instance's linked subconstituencies that has both a human-readable
        display and links to the read views for those subconstituencies (or "None")."""
        delimiter = get_comma_delimiter()
        subconstituencies = self.subconstituencies.distinct()
        if subconstituencies.count() == 0:
            return NO_LINKED_OBJECT
        return format_html_join(delimiter, ANCHOR_SNIPPET, (
            (subconstituency.get_absolute_url(), u'{} - {}'.format(subconstituency.id,
                                                                   subconstituency.name))
            for subconstituency in subconstituencies
        ))


class VumilogFormatterMixin(object):
    @property
    def vumilog_as_html(self):
        """Return HTML for this instance's linked vumilog that has both a human-readable
        display and links to the read views for the vumilog (or "None")."""
        if not self.vumi:
            return NO_LINKED_OBJECT
        return format_html(
            ANCHOR_SNIPPET,
            self.vumi.get_absolute_url(),
            unicode(self.vumi))


class TimestampFormatterMixin(object):
    @property
    def formatted_timestamp(self):
        """Return this instance's timestamp field formatted as per Libyan standards."""
        return self.timestamp.strftime(LIBYA_DATETIME_FORMAT)


class StaffBreadMixin(object):
    """
    Mixin for Bread classes to set the "staff_page" context variable true.
    This will cause the Staff tab at the top of the staff page to be highlighted.
    """
    def get_additional_context_data(self):
        data = super(StaffBreadMixin, self).get_additional_context_data()
        data['staff_page'] = True
        return data
