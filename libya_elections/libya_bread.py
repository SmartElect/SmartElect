import hashlib

from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.sql.datastructures import EmptyResultSet
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.html import format_html, format_html_join

from bread.bread import BrowseView, DeleteView, Bread

from libya_elections.constants import (
    ANCHOR_SNIPPET,
    NO_LINKED_OBJECT,
)
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
    # Set to the number of seconds you'd like the paginator's `count` property to be
    # cached. Set to None to disable. Note `0` means 'never expire' in memcache and
    # should not be used unless that behavior is desired.
    count_cache_timeout = None

    def get_paginator(self, *args, **kwargs):
        paginator = super(PaginatorMixin, self).get_paginator(*args, **kwargs)
        if self.count_cache_timeout is not None:
            try:
                # hashlib expects ascii as input, so safely obtain that here
                query_sql = str(self.get_queryset().query).encode('ascii', errors='replace')
            except EmptyResultSet:
                # EmptyQuerySets (i.e. qs.none()) do not generate valid SQL:
                # https://code.djangoproject.com/ticket/22973#comment:3
                query_sql = b''
            cache_key = 'paginator-count-%s' % hashlib.md5(query_sql).hexdigest()
            # pre-cache paginator._count, if possible
            paginator._count = cache.get(cache_key)
            if paginator._count is None:
                # force paginator to set its own _count cache and save that in memcache
                cache.set(cache_key, paginator.count, self.count_cache_timeout)
        return paginator

    def get_context_data(self, **kwargs):
        data = super(PaginatorMixin, self).get_context_data(**kwargs)
        # get the paginator data structures
        paginator = data['paginator']
        page = data['page_obj']

        if data.get('is_paginated', False):
            # calculate ranges of pages we'll show (paginator list is 1-based)
            head_range = list(range(1, NUM_PAGES_AT_HEAD_OR_TAIL + 1))
            tail_range = list(range(paginator.num_pages - 1, paginator.num_pages + 1))
            surround_range = list(range(page.number - NUM_PAGES_SURROUNDING_CURRENT,
                                        page.number + NUM_PAGES_SURROUNDING_CURRENT + 1))
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


class BallotFormatterMixin(object):
    def ballot_as_html(self):
        """Return HTML for this instance's ballot field that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        if self.ballot is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET, self.ballot.get_absolute_url(),
                           str(self.ballot))


class BirthDateFormatterMixin(object):
    def formatted_birth_date(self):
        """Return this instance's birth_date field formatted as per Libyan standards."""
        try:
            return date_format(self.birth_date, "SHORT_DATE_FORMAT")
        except ValueError:
            return self.birth_date


class CitizenFormatterMixin(object):
    def citizen_as_html(self):
        """Return HTML for this instance's citizen field that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        # avoid circular import
        from civil_registry.models import Citizen
        try:
            citizen = self.citizen
        except Citizen.DoesNotExist:
            # if citizen is missing, then it will not exist in the related queryset
            citizen = None
        if citizen is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET, citizen.get_absolute_url(),
                           str(citizen))


class ConstituencyFormatterMixin(object):
    def constituency_as_html(self):
        """Return HTML for this instance's constituency field that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        if self.constituency is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET,
                           self.constituency.get_absolute_url(),
                           self.constituency_name)


class CreatedByFormatterMixin(object):
    def created_by_as_html(self):
        """Return HTML for this instance's created_by field (User) that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        if self.created_by is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET,
                           # User doesn't have a suitable get_absolute_url()
                           reverse('read_user', args=[self.created_by.id]),
                           str(self.created_by))


class ElectionFormatterMixin(object):
    def election_as_html(self):
        """Return HTML for this instance's election field that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        if self.election is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET, self.election.get_absolute_url(),
                           str(self.election))


class InResponseToFormatterMixin(object):
    def in_response_to_as_html(self):
        """Return HTML for this instance's in_response_to field (SMS) that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        if self.in_response_to is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET, self.in_response_to.get_absolute_url(),
                           str(self.in_response_to))


class OfficeFormatterMixin(object):
    def office_as_html(self):
        """Return HTML for this instance's office field that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        if self.office is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET, self.office.get_absolute_url(),
                           self.office_name)


class ElectionTimesFormatterMixin(object):
    def formatted_polling_start_time(self):
        """Return this instance's polling_start_time field formatted as per Libyan standards."""
        return date_format(self.polling_start_time, "SHORT_DATETIME_FORMAT")

    def formatted_polling_end_time(self):
        """Return this instance's polling_end_time field formatted as per Libyan standards."""
        return date_format(self.polling_end_time, "SHORT_DATETIME_FORMAT")

    def formatted_work_start_time(self):
        """Return this instance's work_start_time field formatted as per Libyan standards."""
        return date_format(self.work_start_time, "SHORT_DATETIME_FORMAT")

    def formatted_work_end_time(self):
        """Return this instance's work_end_time field formatted as per Libyan standards."""
        return date_format(self.work_end_time, "SHORT_DATETIME_FORMAT")


class RegistrationCenterFormatterMixin(object):
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
        return format_html(ANCHOR_SNIPPET, center.get_absolute_url(), str(center))


class ReviewedByFormatterMixin(object):
    def reviewed_by_as_html(self):
        """Return HTML for this instance's reviewed_by field (User) that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        if self.reviewed_by is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET,
                           # User doesn't have a suitable get_absolute_url()
                           reverse('read_user', args=[self.reviewed_by.id]),
                           str(self.reviewed_by))


class SMSFormatterMixin(object):
    def sms_as_html(self):
        """Return HTML for this instance's sms field that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        if self.sms is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET, self.sms.get_absolute_url(),
                           str(self.sms))


class StartEndTimeFormatterMixin(object):
    def formatted_end_time(self):
        """Return this instance's end_time field formatted as per Libyan standards."""
        if self.end_time:
            return date_format(self.end_time, "SHORT_DATETIME_FORMAT")
        else:
            return NO_LINKED_OBJECT

    def formatted_start_time(self):
        """Return this instance's start_time field formatted as per Libyan standards."""
        if self.start_time:
            return date_format(self.start_time, "SHORT_DATETIME_FORMAT")
        else:
            return NO_LINKED_OBJECT


class SubconstituencyFormatterMixin(object):
    def subconstituency_as_html(self):
        """Return HTML for this instance's subconstituency field that has both a human-readable
        display and a link to the read view for that field (or "None")."""
        if self.subconstituency is None:
            return NO_LINKED_OBJECT
        return format_html(ANCHOR_SNIPPET, self.subconstituency.get_absolute_url(),
                           self.subconstituency_name)


class SubconstituenciesFormatterMixin(object):
    def subconstituencies_as_html(self):
        """Return HTML for this instance's linked subconstituencies that has both a human-readable
        display and links to the read views for those subconstituencies (or "None")."""
        delimiter = get_comma_delimiter()
        subconstituencies = self.subconstituencies.distinct()
        if subconstituencies.count() == 0:
            return NO_LINKED_OBJECT
        return format_html_join(delimiter, ANCHOR_SNIPPET, (
            (subconstituency.get_absolute_url(), '{} - {}'.format(subconstituency.id,
                                                                  subconstituency.name))
            for subconstituency in subconstituencies
        ))


class VumilogFormatterMixin(object):
    def vumilog_as_html(self):
        """Return HTML for this instance's linked vumilog that has both a human-readable
        display and links to the read views for the vumilog (or "None")."""
        if not self.vumi:
            return NO_LINKED_OBJECT
        return format_html(
            ANCHOR_SNIPPET,
            self.vumi.get_absolute_url(),
            str(self.vumi))


class TimestampFormatterMixin(object):
    def formatted_timestamp(self):
        """Return this instance's timestamp field formatted as per Libyan standards."""
        return date_format(self.timestamp, "SHORT_DATETIME_FORMAT")


class StaffBreadMixin(object):
    """
    Mixin for Bread classes to set the "staff_page" context variable true.
    This will cause the Staff tab at the top of the staff page to be highlighted.
    """
    def get_additional_context_data(self):
        data = super(StaffBreadMixin, self).get_additional_context_data()
        data['staff_page'] = True
        return data
