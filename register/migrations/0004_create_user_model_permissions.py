# -*- coding: utf-8 -*-
from __future__ import unicode_literals

# Need to create 'browse_user' and 'read_user' permissions for User models

from django.conf import settings
from django.db import migrations

from libya_elections.utils import get_permission_object_by_name

def create_permission(apps, schema_editor):
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    get_permission_object_by_name('auth.browse_user', Permission, ContentType, create_if_needed=True)
    get_permission_object_by_name('auth.read_user', Permission, ContentType, create_if_needed=True)


def no_op(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('register', '0003_fixtures'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(create_permission, no_op)
    ]
