# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import libya_elections.phone_numbers
from decimal import Decimal
import django.db.models.deletion
import django.utils.timezone
import django.core.validators
import libya_elections.libya_bread


class Migration(migrations.Migration):

    dependencies = [
        ('civil_registry', '__first__'),
        ('rapidsms', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Blacklist',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='creation date', editable=False)),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='modification date', editable=False)),
                ('phone_number', libya_elections.phone_numbers.PhoneNumberField(db_index=True, max_length=13, verbose_name='phone number')),
            ],
            options={
                'ordering': ['phone_number'],
                'verbose_name': 'blacklisted number',
                'verbose_name_plural': 'blacklisted numbers',
                'permissions': (('read_blacklist', 'Can read black list'), ('browse_blacklist', 'Can browse black list')),
            },
            bases=(libya_elections.phone_numbers.FormattedPhoneNumberMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Constituency',
            fields=[
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='creation date', editable=False)),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='modification date', editable=False)),
                ('id', models.IntegerField(serialize=False, verbose_name='id', primary_key=True)),
                ('name_english', models.CharField(max_length=128, verbose_name='name (English)')),
                ('name_arabic', models.CharField(max_length=128, verbose_name='name (Arabic)')),
            ],
            options={
                'ordering': ['id'],
                'abstract': False,
                'verbose_name': 'constituency',
                'verbose_name_plural': 'constituencies',
                'permissions': (('read_constituency', 'Can read constituency'), ('browse_constituency', 'Can browse constituencies')),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Office',
            fields=[
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='creation date', editable=False)),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='modification date', editable=False)),
                ('id', models.IntegerField(serialize=False, verbose_name='id', primary_key=True)),
                ('name_english', models.CharField(max_length=128, verbose_name='name (English)')),
                ('name_arabic', models.CharField(max_length=128, verbose_name='name (Arabic)')),
                ('region', models.IntegerField(default=0, verbose_name='region', choices=[(0, 'No Region'), (1, 'West'), (2, 'South'), (3, 'East')])),
            ],
            options={
                'ordering': ['id'],
                'abstract': False,
                'verbose_name': 'office',
                'verbose_name_plural': 'offices',
                'permissions': (('read_office', 'Can read office'), ('browse_office', 'Can browse offices')),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='creation date', editable=False)),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='modification date', editable=False)),
                ('blocked', models.BooleanField(default=False, help_text='Whether this person is blocked from registering and voting', verbose_name='blocked')),
                ('citizen', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, verbose_name='citizen', to='civil_registry.Citizen', help_text='Uniquely identifies a person, even across changes of national ID')),
            ],
            options={
                'verbose_name': 'person',
                'verbose_name_plural': 'people',
                'permissions': (('read_person', 'Can read person'),),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Registration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='creation date', editable=False)),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='modification date', editable=False)),
                ('archive_time', models.DateTimeField(default=None, help_text='If non-NULL, from this time on, this record is no longer in effect.', null=True, verbose_name='archive time', blank=True)),
                ('change_count', models.IntegerField(default=0, help_text='The number of times this registration has been changed after it was initially made (original registration not counted). ', verbose_name='change count')),
                ('max_changes', models.IntegerField(default=3, help_text='The number of times this registration is allowed to be changed after it was initially made. Defaults to 3, but can be increased.', verbose_name='max changes')),
                ('repeat_count', models.IntegerField(default=1, help_text='The number of times messages have been received for this exact registration. The first message is counted, so the 2nd time we see the same registration, the count becomes 2, and so forth. This is reset each time the registration is changed.', verbose_name='repeat count')),
                ('unlocked_until', models.DateTimeField(help_text="If this is set and the current datetime is earlier than this value, allow changing this registration from any phone, even if it's not the phone previously used.", null=True, verbose_name='unlocked until', blank=True)),
                ('citizen', models.ForeignKey(related_name='registrations', verbose_name='citizen', to='civil_registry.Citizen')),
            ],
            options={
                'verbose_name': 'registration',
                'verbose_name_plural': 'registrations',
                'permissions': (('read_registration', 'Can read registration'), ('browse_registration', 'Can browse registration')),
            },
            bases=(libya_elections.libya_bread.CitizenFormatterMixin, libya_elections.libya_bread.RegistrationCenterFormatterMixin, libya_elections.libya_bread.SMSFormatterMixin, models.Model),
        ),
        migrations.CreateModel(
            name='RegistrationCenter',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='creation date', editable=False)),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='modification date', editable=False)),
                ('center_id', models.IntegerField(db_index=True, verbose_name='center id', validators=[django.core.validators.MinValueValidator(10000), django.core.validators.MaxValueValidator(99999)])),
                ('name', models.CharField(max_length=255, verbose_name='name')),
                ('mahalla_name', models.CharField(max_length=255, verbose_name='mahalla name', blank=True)),
                ('village_name', models.CharField(max_length=255, verbose_name='village name', blank=True)),
                ('center_type', models.PositiveSmallIntegerField(default=1, verbose_name='type', choices=[(1, 'General'), (2, 'Displaced'), (3, 'Oil'), (4, 'Disability'), (5, 'Revolution'), (6, 'Copy'), (7, 'Split')])),
                ('center_lat', models.DecimalField(decimal_places=8, validators=[django.core.validators.MaxValueValidator(Decimal('90.0')), django.core.validators.MinValueValidator(Decimal('-90.0'))], max_digits=11, blank=True, null=True, verbose_name='latitude')),
                ('center_lon', models.DecimalField(decimal_places=8, validators=[django.core.validators.MaxValueValidator(Decimal('180.0')), django.core.validators.MinValueValidator(Decimal('-180.0'))], max_digits=11, blank=True, null=True, verbose_name='longitude')),
                ('reg_open', models.BooleanField(default=True, verbose_name='support for registrations')),
                ('constituency', models.ForeignKey(default=999, verbose_name='constituency', to='register.Constituency')),
                ('copy_of', models.ForeignKey(related_name='copied_by', default=None, blank=True, to='register.RegistrationCenter', null=True, verbose_name='copy of')),
                ('office', models.ForeignKey(default=999, verbose_name='office', to='register.Office')),
            ],
            options={
                'ordering': ['center_id'],
                'verbose_name': 'registration center',
                'verbose_name_plural': 'registration centers',
                'permissions': (('read_registrationcenter', 'Can view registration center'), ('browse_registrationcenter', 'Can browse registration centers')),
            },
            bases=(libya_elections.libya_bread.ConstituencyFormatterMixin, libya_elections.libya_bread.OfficeFormatterMixin, libya_elections.libya_bread.SubconstituencyFormatterMixin, models.Model),
        ),
        migrations.CreateModel(
            name='SMS',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='creation date', editable=False)),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='modification date', editable=False)),
                ('from_number', models.CharField(max_length=15, verbose_name='from number', db_index=True)),
                ('to_number', models.CharField(max_length=15, verbose_name='to number', db_index=True)),
                ('direction', models.IntegerField(db_index=True, verbose_name='direction', choices=[(1, 'Incoming'), (2, 'Outgoing')])),
                ('msg_type', models.IntegerField(verbose_name='message type', choices=[(3, 'Registration'), (5, 'Invalid format'), (6, 'Multiple problems'), (7, 'Invalid registration centre code length'), (8, 'No such registration centre found'), (9, 'Not enough enough National ID digits'), (11, 'Invalid valid National ID'), (13, 'Unknown'), (14, 'Registration update'), (15, 'Registration Center query'), (16, 'Invalid Form ID'), (17, 'Phone activation'), (18, 'Daily Report'), (19, 'Daily Report invalid'), (20, 'Bulk Outgoing Message'), (21, 'Polling Report'), (22, 'Polling Report invalid'), (23, 'Phone number not activated')])),
                ('order', models.IntegerField(null=True, verbose_name='order', blank=True)),
                ('message', models.TextField(verbose_name='message', db_index=True)),
                ('message_code', models.IntegerField(default=0, help_text="If we're sending one of our canned messages, this is the message code.", verbose_name='message code', db_index=True)),
                ('uuid', models.CharField(db_index=True, max_length=50, verbose_name='uuid', blank=True)),
                ('is_audited', models.BooleanField(default=False, db_index=True, verbose_name='is audited')),
                ('need_to_anonymize', models.BooleanField(default=False, db_index=True, verbose_name='need to anonymize')),
                ('carrier', models.ForeignKey(verbose_name='carrier', to='rapidsms.Backend')),
                ('citizen', models.ForeignKey(related_name='messages', verbose_name='citizen', blank=True, to='civil_registry.Citizen', null=True)),
                ('in_response_to', models.ForeignKey(related_name='responses', verbose_name='in response to', blank=True, to='register.SMS', null=True)),
            ],
            options={
                'verbose_name': 'sms',
                'verbose_name_plural': 'smses',
                'permissions': (('read_sms', 'Can read sms'), ('browse_sms', 'Can browse sms')),
            },
            bases=(libya_elections.libya_bread.CitizenFormatterMixin, libya_elections.libya_bread.InResponseToFormatterMixin, models.Model),
        ),
        migrations.CreateModel(
            name='SubConstituency',
            fields=[
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='creation date', editable=False)),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='modification date', editable=False)),
                ('id', models.IntegerField(serialize=False, verbose_name='id', primary_key=True)),
                ('name_english', models.CharField(max_length=128, verbose_name='name (English)')),
                ('name_arabic', models.CharField(max_length=128, verbose_name='name (Arabic)')),
            ],
            options={
                'ordering': ['id'],
                'abstract': False,
                'verbose_name': 'subconstituency',
                'verbose_name_plural': 'subconstituencies',
                'permissions': (('read_subconstituency', 'Can read subconstituency'), ('browse_subconstituency', 'Can browse subconstituencies')),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Whitelist',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='creation date', editable=False)),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='modification date', editable=False)),
                ('phone_number', libya_elections.phone_numbers.PhoneNumberField(db_index=True, max_length=13, verbose_name='phone number')),
            ],
            options={
                'ordering': ['phone_number'],
                'verbose_name': 'whitelisted number',
                'verbose_name_plural': 'whitelisted numbers',
                'permissions': (('read_whitelist', 'Can read whitelist'), ('browse_whitelist', 'Can browse whitelist')),
            },
            bases=(libya_elections.phone_numbers.FormattedPhoneNumberMixin, models.Model),
        ),
        migrations.AddField(
            model_name='registrationcenter',
            name='subconstituency',
            field=models.ForeignKey(related_name='registration_centers', default=999, verbose_name='subconstituency', to='register.SubConstituency'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='registration',
            name='registration_center',
            field=models.ForeignKey(verbose_name='registration center', to='register.RegistrationCenter'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='registration',
            name='sms',
            field=models.ForeignKey(related_name='registrations', verbose_name='sms', to='register.SMS'),
            preserve_default=True,
        ),
    ]
