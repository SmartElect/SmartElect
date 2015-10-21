from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from libya_site.tests.factories import UserFactory


class StaffUserMixin(object):
    model = None
    username = "staff_user"
    email = "staff@example.com"
    password = "password"
    permissions = []

    def setUp(self):
        self.user = self.create_staff_user()
        self.login(self.user)

    def create_staff_user(self):
        user = UserFactory(username=self.username, email=self.email, password=self.password)
        user.is_staff = True
        user.save()
        if self.model:
            content_type = ContentType.objects.get_for_model(self.model)
            for perm in self.permissions:
                user.user_permissions.add(Permission.objects.get(content_type=content_type,
                                                                 codename=perm))
        return user

    def login(self, user):
        self.client.login(username=user.username, password=self.password)
