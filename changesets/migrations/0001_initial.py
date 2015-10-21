# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('register', '__first__'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('civil_registry', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChangeRecord',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='creation date', editable=False)),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='modification date', editable=False)),
                ('changed', models.BooleanField(default=True, help_text='Whether change was made', verbose_name='changed')),
                ('change', models.IntegerField(verbose_name='change', choices=[(1, 'Move voters to another polling center'), (2, 'Block voters'), (3, 'Unblock voters'), (4, 'Roll back another changeset')])),
            ],
            options={
                'verbose_name': 'change record',
                'verbose_name_plural': 'change records',
                'permissions': [('browse_changerecord', 'Browse changerecords')],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Changeset',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='creation date', editable=False)),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='modification date', editable=False)),
                ('name', models.CharField(unique=True, max_length=256, verbose_name='name')),
                ('change', models.IntegerField(default=1, verbose_name='change', choices=[(1, 'Move voters to another polling center'), (2, 'Block voters'), (3, 'Unblock voters'), (4, 'Roll back another changeset')])),
                ('how_to_select', models.IntegerField(default=1, help_text='How to select affected voters. If you select another changeset, it will change the same voters who were changed in the other changeset, which might NOT be the same as using the same rules for selecting voters that the other changeset used.', verbose_name='how to select', choices=[(1, 'Select a list of polling centers'), (2, 'Upload a list of national IDs'), (3, 'Select another changeset')])),
                ('message', models.CharField(default='', help_text='Optional text message to send to affected voters after applying change', max_length=1024, verbose_name='message', blank=True)),
                ('justification', models.TextField(help_text='Reason for the changes. Include references to legal justification for the changes if possible.', verbose_name='justification')),
                ('execution_start_time', models.DateTimeField(help_text='When execution of the changeset started.', verbose_name='start time', null=True, editable=False, blank=True)),
                ('finish_time', models.DateTimeField(verbose_name='finish time', null=True, editable=False, blank=True)),
                ('status', models.IntegerField(default=1, verbose_name='status', choices=[(1, 'New - not approved'), (2, 'Approved - not started'), (3, 'Started - start button has been pressed but processing has not begun'), (4, 'Executing - being processed'), (5, 'Failed - had errors, changes were not made'), (6, 'Successful - completed without errors and not rolled back'), (7, 'Partially successful - rollback was not able to rollback all changes'), (8, 'Rolled back - some or all changes have been rolled back')])),
                ('error_text', models.TextField(default='', help_text='If the changes failed, this will contain the error message(s).', verbose_name='error text', blank=True)),
                ('approvers', models.ManyToManyField(related_name='changeset_approvals', verbose_name='approvers', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(related_name='changesets_created', on_delete=django.db.models.deletion.PROTECT, verbose_name='created by', to=settings.AUTH_USER_MODEL)),
                ('other_changeset', models.ForeignKey(related_name='target_changesets', blank=True, to='changesets.Changeset', help_text='Another changeset to select voters from or to roll back.', null=True, verbose_name='other changeset')),
                ('queued_by', models.ForeignKey(related_name='changesets_queued', on_delete=django.db.models.deletion.PROTECT, blank=True, to=settings.AUTH_USER_MODEL, help_text='The user who queued the changeset for execution.', null=True, verbose_name='queued by')),
                ('rollback_changeset', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, blank=True, to='changesets.Changeset', help_text='If this changeset has been rolled back, this is the changeset that did it.', null=True, verbose_name='rollback changeset')),
                ('selected_centers', models.ManyToManyField(related_name='changesets_from', null=True, verbose_name='selected centers', to='register.RegistrationCenter', blank=True)),
                ('selected_citizens', models.ManyToManyField(related_name='changesets_selected', null=True, verbose_name='selected citizens', to='civil_registry.Citizen', blank=True)),
                ('target_center', models.ForeignKey(related_name='changesets_to', on_delete=django.db.models.deletion.PROTECT, verbose_name='target center', blank=True, to='register.RegistrationCenter', null=True)),
            ],
            options={
                'ordering': ['-creation_date'],
                'verbose_name': 'changeset',
                'verbose_name_plural': 'changesets',
                'permissions': [('approve_changeset', 'Approve changeset'), ('queue_changeset', 'Start changeset'), ('browse_changeset', 'Browse changesets'), ('read_changeset', 'Read changeset')],
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='changerecord',
            name='changeset',
            field=models.ForeignKey(related_name='change_records', on_delete=django.db.models.deletion.PROTECT, verbose_name='changeset', to='changesets.Changeset'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='changerecord',
            name='citizen',
            field=models.ForeignKey(related_name='change_records', on_delete=django.db.models.deletion.PROTECT, verbose_name='citizen', to='civil_registry.Citizen'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='changerecord',
            name='from_center',
            field=models.ForeignKey(related_name='changes_made_from', on_delete=django.db.models.deletion.PROTECT, verbose_name='from center', blank=True, to='register.RegistrationCenter', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='changerecord',
            name='to_center',
            field=models.ForeignKey(related_name='changes_made_to', on_delete=django.db.models.deletion.PROTECT, verbose_name='to center', blank=True, to='register.RegistrationCenter', null=True),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='changerecord',
            unique_together=set([('changeset', 'citizen')]),
        ),
    ]
