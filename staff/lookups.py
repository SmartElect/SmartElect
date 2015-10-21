from django.contrib.auth import get_user_model
from selectable.base import ModelLookup
from selectable.registry import registry


class StaffUserLookup(ModelLookup):
    filters = {
        'is_staff': True,
    }
    model = get_user_model()
    search_fields = (
        'username__icontains',
        'first_name__icontains',
        'last_name__icontains',
        'email__icontains',
    )


registry.register(StaffUserLookup)
