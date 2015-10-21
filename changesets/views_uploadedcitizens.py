from bread.bread import Bread
from django.utils.translation import ugettext_lazy as _
from changesets.models import Changeset
from civil_registry.models import Citizen
from libya_elections.libya_bread import PaginatedBrowseView


class UploadedCitizenBrowse(PaginatedBrowseView):
    columns = [
        (_('National ID'), 'national_id'),
        (_('Name'), 'format_name'),
    ]
    template_name = 'changesets/uploadedcitizen_browse.html'

    def get_changeset(self):
        changeset_pk = self.request.GET.get('changeset', None)
        if changeset_pk:
            return Changeset.objects.get(pk=changeset_pk)

    def get_queryset(self):
        changeset = self.get_changeset()
        if changeset:
            return changeset.selected_citizens.all()
        else:
            return Citizen.objects.none()

    def get_context_data(self, **kwargs):
        context = super(UploadedCitizenBrowse, self).get_context_data(**kwargs)
        context['changeset'] = self.get_changeset()
        return context


class UploadedCitizenBread(Bread):
    browse_view = UploadedCitizenBrowse
    model = Citizen
    name = 'uploadedcitizen'
    plural_name = 'uploadedcitizens'
    views = 'B'
