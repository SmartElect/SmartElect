# Python standard library

# 3rd party
from bread.bread import Bread, LabelValueReadView
from django.utils.translation import ugettext_lazy as _

# Our own modules
from civil_registry.models import Citizen
from libya_elections.libya_bread import PaginatedBrowseView, StaffBreadMixin
from libya_elections.utils import get_verbose_name


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
