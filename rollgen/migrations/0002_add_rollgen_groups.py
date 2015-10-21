# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def add_rollgen_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')

    Group.objects.get_or_create(name='rollgen_view_job')
    Group.objects.get_or_create(name='rollgen_create_job')

def remove_rollgen_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')

    for name in ('rollgen_view_job', 'rollgen_create_job'):
        try:
            group = Group.objects.get(name=name)
        except Group.DoesNotExistError:
            group = None

        if group:
            group.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('rollgen', '0001_initial'),
        ('auth', '__first__'),
    ]

    operations = [
        migrations.RunPython(add_rollgen_groups, reverse_code=remove_rollgen_groups),
    ]
