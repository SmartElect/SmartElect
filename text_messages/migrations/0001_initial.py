# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MessageText',
            fields=[
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='creation date', editable=False)),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='modification date', editable=False)),
                ('number', models.IntegerField(serialize=False, verbose_name='number', primary_key=True)),
                ('label', models.CharField(max_length=80, verbose_name='label')),
                ('msg_en', models.TextField(max_length=512, verbose_name='english')),
                ('msg_ar', models.TextField(max_length=512, verbose_name='arabic')),
                ('enhanced_en', models.TextField(default=b'', max_length=512, verbose_name='english repeat message', blank=True)),
                ('enhanced_ar', models.TextField(default=b'', max_length=512, verbose_name='arabic repeat message', blank=True)),
                ('description', models.TextField(default=b'', verbose_name='description', blank=True)),
                ('last_updated_by', models.ForeignKey(verbose_name='last updated by', to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'ordering': ['number'],
                'verbose_name': 'message text',
                'verbose_name_plural': 'message texts',
            },
            bases=(models.Model,),
        ),
    ]
