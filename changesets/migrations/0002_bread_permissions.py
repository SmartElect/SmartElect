# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from changesets.models import CHANGE_CHANGESETS_GROUP, APPROVE_CHANGESET_PERMISSION, \
    QUEUE_CHANGESET_PERMISSION, BROWSE_CHANGESETS_PERMISSION, READ_CHANGESET_PERMISSION, \
    EDIT_CHANGESET_PERMISSION, ADD_CHANGESET_PERMISSION, DELETE_CHANGESET_PERMISSION, \
    APPROVE_CHANGESETS_GROUP, QUEUE_CHANGESETS_GROUP
from libya_elections.utils import get_permission_object_by_name


def changeset_permissions(apps, schema_editor):
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Group = apps.get_model('auth', 'Group')

    # Make sure there's a group "ApproveChangesets" and another one
    # "QueueChangesets"
    change_changesets_group, __ = Group.objects.get_or_create(name=CHANGE_CHANGESETS_GROUP)
    approve_changesets_group, __ = Group.objects.get_or_create(name=APPROVE_CHANGESETS_GROUP)
    queue_changesets_group, __ = Group.objects.get_or_create(name=QUEUE_CHANGESETS_GROUP)

    # Useful permissions
    approve_changeset_permission = get_permission_object_by_name(
        APPROVE_CHANGESET_PERMISSION, Permission, ContentType, True)
    queue_changeset_permission = get_permission_object_by_name(
        QUEUE_CHANGESET_PERMISSION, Permission, ContentType, True)

    browse_permission = get_permission_object_by_name(BROWSE_CHANGESETS_PERMISSION, Permission, ContentType, True)
    read_permission = get_permission_object_by_name(READ_CHANGESET_PERMISSION, Permission, ContentType, True)
    edit_permission = get_permission_object_by_name(EDIT_CHANGESET_PERMISSION, Permission, ContentType, True)
    add_permission = get_permission_object_by_name(ADD_CHANGESET_PERMISSION, Permission, ContentType, True)
    delete_permission = get_permission_object_by_name(DELETE_CHANGESET_PERMISSION, Permission, ContentType, True)

    browse_changerecords_permission = get_permission_object_by_name('changesets.browse_changerecord', Permission, ContentType, True)
    browse_citizens_permission = get_permission_object_by_name('civil_registry.browse_citizen', Permission, ContentType, True)

    change_changesets_group.permissions.add(
        browse_permission,
        read_permission,
        edit_permission,
        add_permission,
        delete_permission,
        browse_changerecords_permission,
        browse_citizens_permission,
    )
    approve_changesets_group.permissions.add(
        approve_changeset_permission,
        browse_permission,
        read_permission,
        edit_permission,
        add_permission,
        delete_permission,
        browse_changerecords_permission,
        browse_citizens_permission,
    )
    queue_changesets_group.permissions.add(
        queue_changeset_permission,
        browse_permission,
        read_permission,
        edit_permission,
        add_permission,
        delete_permission,
        browse_changerecords_permission,
        browse_citizens_permission,
    )


def no_op(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('changesets', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(changeset_permissions, no_op),
    ]
