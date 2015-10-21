# Python standard library
from datetime import datetime

# 3rd party
from braces.views import JSONResponseMixin
from bread.bread import Bread, LabelValueReadView
from django.db.models import Max, Min
from django.http import Http404
from django.utils.translation import ugettext_lazy as _
from django.views.generic import View

# Our own modules
from civil_registry.models import Citizen, CitizenMetadata
from civil_registry.utils import get_citizen_by_national_id
from libya_elections.constants import FEMALE
from libya_elections.libya_bread import PaginatedBrowseView, StaffBreadMixin
from libya_elections.utils import get_verbose_name


def format_date(date_obj):
    """
    Return the date formatted as a date/time string in ISO format
    e.g. "1990-07-28T00:00:00"

    (Time is always 0:00)
    """
    datetime_obj = datetime(year=date_obj.year, month=date_obj.month, day=date_obj.day)
    return datetime_obj.isoformat()


def format_datetime(datetime_obj):
    """
    Return the date formatted as a date/time string in ISO format
    e.g. "1990-07-28T00:00:00"
    """
    return datetime_obj.isoformat()


# Note: these are protected by basic auth; see urls.py
class GetVoterView(JSONResponseMixin, View):
    """
    API to let clients look up voters by national ID.
    Response is the voter data in JSON.
    """
    def get(self, request, *args, **kwargs):
        obj = get_citizen_by_national_id(national_id=long(kwargs['voter_id']))
        if not obj:
            raise Http404

        result = dict(
            person_id=obj.civil_registry_id,
            national_id=obj.national_id,
            first_name=obj.first_name,
            father_name=obj.father_name,
            grandfather_name=obj.grandfather_name,
            mother_name=obj.mother_name,
            family_name=obj.family_name,
            gender='F' if obj.gender == FEMALE else 'M',
            registry_number=obj.fbr_number,
            birth_date=format_date(obj.birth_date),
        )
        return self.render_json_response(result)


class GetMetadataView(JSONResponseMixin, View):
    """
    API to let clients find out how many voters are in the database,
    what the date of the most recent data is, and what the minimum
    and maximum national IDs in the database are.
    Returns a JSON dictionary.

    Note that missing citizens are not counted.
    """
    def get(self, request, *args, **kwargs):
        result = dict(
            num_rows=Citizen.objects.count(),
        )
        if result['num_rows']:
            result.update(
                **Citizen.objects.aggregate(max_id=Max('national_id'), min_id=Min('national_id'))
            )
        try:
            metadata = CitizenMetadata.objects.get()
        except CitizenMetadata.DoesNotExist:
            pass
        else:
            result['dump_date'] = format_datetime(metadata.dump_time)
        return self.render_json_response(result)


class CitizenBrowse(PaginatedBrowseView):
    columns = [
        (_('National ID'), 'national_id'),
        (_('Gender'), 'get_gender_display', 'gender'),
        (_('First name'), 'first_name'),
        (_("Father's name"), 'father_name'),
        (_("Grandfather's name"), 'grandfather_name'),
        (_('Family name'), 'family_name'),
        (_("Mother's name"), 'mother_name'),
        (_('Birth date'), 'formatted_birth_date', 'birth_date'),
    ]
    search_fields = ['national_id', 'fbr_number', 'first_name', 'father_name',
                     'grandfather_name', 'family_name', 'mother_name', ]
    search_terms = _("National ID, FBR number, First name, Father's name, Mother's name, "
                     "Grandfather's name, or Family name")


class CitizenRead(LabelValueReadView):
    fields = ((None, 'civil_registry_id'),
              (None, 'national_id'),
              (None, 'fbr_number'),
              (None, 'first_name'),
              (None, 'father_name'),
              (None, 'grandfather_name'),
              (None, 'family_name'),
              (None, 'mother_name'),
              (get_verbose_name(Citizen, 'birth_date'), 'formatted_birth_date'),
              (get_verbose_name(Citizen, 'gender'), 'gender_formatted'),
              (None, 'address'),
              (None, 'office_id'),
              (None, 'branch_id'),
              (None, 'state'),
              (_("Blocked"), 'blocked'),
              )


class CitizenBread(StaffBreadMixin, Bread):
    browse_view = CitizenBrowse
    read_view = CitizenRead
    model = Citizen
    exclude = ['deleted']
    views = 'BR'
