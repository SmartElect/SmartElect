# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone
import libya_elections.libya_bread


class Migration(migrations.Migration):

    dependencies = [
        ('voting', '__first__'),
        ('register', '0003_fixtures'),
    ]

    operations = [
        migrations.CreateModel(
            name='Station',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='creation date', editable=False)),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='modification date', editable=False)),
                ('number', models.PositiveSmallIntegerField(verbose_name='number')),
                ('gender', models.PositiveSmallIntegerField(verbose_name='gender')),
                ('n_registrants', models.IntegerField(verbose_name='number of registrants')),
                ('first_voter_name', models.CharField(max_length=255, verbose_name='first voter name')),
                ('first_voter_number', models.IntegerField(verbose_name='first voter number')),
                ('last_voter_name', models.CharField(max_length=255, verbose_name='last voter name')),
                ('last_voter_number', models.IntegerField(verbose_name='last voter number')),
                ('center', models.ForeignKey(verbose_name='registration center', to='register.RegistrationCenter')),
                ('election', models.ForeignKey(verbose_name='election', to='voting.Election')),
            ],
            options={
                'ordering': ('center__center_id', 'number'),
                'verbose_name': 'station',
                'verbose_name_plural': 'stations',
                'permissions': [('browse_station', 'Can list stations'), ('read_station', 'Can read a station')],
            },
            bases=(libya_elections.libya_bread.ElectionFormatterMixin, libya_elections.libya_bread.RegistrationCenterFormatterMixin, models.Model),
        ),
        migrations.AlterUniqueTogether(
            name='station',
            unique_together=set([('election', 'center', 'number')]),
        ),
    ]
