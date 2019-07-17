from selectable.base import ModelLookup
from selectable.registry import registry

from register.models import RegistrationCenter


class RegistrationCenterLookup(ModelLookup):
    filters = {
        'deleted': False,
    }
    model = RegistrationCenter
    search_fields = ('name__icontains', 'center_id__icontains')

    def get_queryset(self):
        return super().get_queryset().all()


registry.register(RegistrationCenterLookup)
