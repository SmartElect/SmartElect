# Generated by Django 2.2 on 2019-05-03 14:04

from decimal import Decimal
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import libya_elections.libya_bread
import libya_elections.phone_numbers


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('rapidsms', '__first__'),
        ('civil_registry', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='Blacklist',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='creation date')),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='modification date')),
                ('phone_number', libya_elections.phone_numbers.PhoneNumberField(db_index=True, max_length=13, verbose_name='phone number')),
            ],
            options={
                'verbose_name': 'blacklisted number',
                'verbose_name_plural': 'blacklisted numbers',
                'ordering': ['phone_number'],
                'permissions': (('read_blacklist', 'Can read black list'), ('browse_blacklist', 'Can browse black list')),
            },
            bases=(libya_elections.phone_numbers.FormattedPhoneNumberMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Constituency',
            fields=[
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='creation date')),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='modification date')),
                ('id', models.IntegerField(primary_key=True, serialize=False, verbose_name='id')),
                ('name_english', models.CharField(max_length=128, verbose_name='name (English)')),
                ('name_arabic', models.CharField(max_length=128, verbose_name='name (Arabic)')),
            ],
            options={
                'verbose_name': 'constituency',
                'verbose_name_plural': 'constituencies',
                'ordering': ['id'],
                'permissions': (('read_constituency', 'Can read constituency'), ('browse_constituency', 'Can browse constituencies')),
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Office',
            fields=[
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='creation date')),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='modification date')),
                ('id', models.IntegerField(primary_key=True, serialize=False, verbose_name='id')),
                ('name_english', models.CharField(max_length=128, verbose_name='name (English)')),
                ('name_arabic', models.CharField(max_length=128, verbose_name='name (Arabic)')),
                ('region', models.IntegerField(choices=[(0, 'No Region'), (1, 'West'), (2, 'South'), (3, 'East')], default=0, verbose_name='region')),
            ],
            options={
                'verbose_name': 'office',
                'verbose_name_plural': 'offices',
                'ordering': ['id'],
                'permissions': (('read_office', 'Can read office'), ('browse_office', 'Can browse offices')),
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SubConstituency',
            fields=[
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='creation date')),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='modification date')),
                ('id', models.IntegerField(primary_key=True, serialize=False, verbose_name='id')),
                ('name_english', models.CharField(max_length=128, verbose_name='name (English)')),
                ('name_arabic', models.CharField(max_length=128, verbose_name='name (Arabic)')),
            ],
            options={
                'verbose_name': 'subconstituency',
                'verbose_name_plural': 'subconstituencies',
                'ordering': ['id'],
                'permissions': (('read_subconstituency', 'Can read subconstituency'), ('browse_subconstituency', 'Can browse subconstituencies')),
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Whitelist',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='creation date')),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='modification date')),
                ('phone_number', libya_elections.phone_numbers.PhoneNumberField(db_index=True, max_length=13, verbose_name='phone number')),
            ],
            options={
                'verbose_name': 'whitelisted number',
                'verbose_name_plural': 'whitelisted numbers',
                'ordering': ['phone_number'],
                'permissions': (('read_whitelist', 'Can read whitelist'), ('browse_whitelist', 'Can browse whitelist')),
            },
            bases=(libya_elections.phone_numbers.FormattedPhoneNumberMixin, models.Model),
        ),
        migrations.CreateModel(
            name='SMS',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='creation date')),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='modification date')),
                ('from_number', models.CharField(db_index=True, max_length=15, verbose_name='from number')),
                ('to_number', models.CharField(db_index=True, max_length=15, verbose_name='to number')),
                ('direction', models.IntegerField(choices=[(1, 'Incoming'), (2, 'Outgoing')], db_index=True, verbose_name='direction')),
                ('msg_type', models.IntegerField(choices=[(3, 'Registration'), (5, 'Invalid format'), (6, 'Multiple problems'), (7, 'Invalid registration centre code length'), (8, 'No such registration centre found'), (9, 'Not enough enough National ID digits'), (11, 'Invalid valid National ID'), (13, 'Unknown'), (14, 'Registration update'), (15, 'Registration Center query'), (16, 'Invalid Form ID'), (17, 'Phone activation'), (18, 'Daily Report'), (19, 'Daily Report invalid'), (20, 'Bulk Outgoing Message'), (21, 'Polling Report'), (22, 'Polling Report invalid'), (23, 'Phone number not activated')], verbose_name='message type')),
                ('order', models.IntegerField(blank=True, null=True, verbose_name='order')),
                ('message', models.TextField(db_index=True, verbose_name='message')),
                ('message_code', models.IntegerField(db_index=True, default=0, help_text="If we're sending one of our canned messages, this is the message code.", verbose_name='message code')),
                ('uuid', models.CharField(blank=True, db_index=True, max_length=50, verbose_name='uuid')),
                ('is_audited', models.BooleanField(db_index=True, default=False, verbose_name='is audited')),
                ('need_to_anonymize', models.BooleanField(db_index=True, default=False, verbose_name='need to anonymize')),
                ('carrier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='rapidsms.Backend', verbose_name='carrier')),
                ('citizen', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='civil_registry.Citizen', verbose_name='citizen')),
                ('in_response_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='responses', to='register.SMS', verbose_name='in response to')),
            ],
            options={
                'verbose_name': 'sms',
                'verbose_name_plural': 'smses',
                'ordering': ['-creation_date'],
                'permissions': (('read_sms', 'Can read sms'), ('browse_sms', 'Can browse sms')),
            },
            bases=(libya_elections.libya_bread.CitizenFormatterMixin, libya_elections.libya_bread.InResponseToFormatterMixin, models.Model),
        ),
        migrations.CreateModel(
            name='RegistrationCenter',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='creation date')),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='modification date')),
                ('center_id', models.IntegerField(db_index=True, validators=[django.core.validators.MinValueValidator(10000), django.core.validators.MaxValueValidator(99999)], verbose_name='center id')),
                ('name', models.CharField(max_length=255, verbose_name='name')),
                ('mahalla_name', models.CharField(blank=True, max_length=255, verbose_name='mahalla name')),
                ('village_name', models.CharField(blank=True, max_length=255, verbose_name='village name')),
                ('center_type', models.PositiveSmallIntegerField(choices=[(1, 'General'), (2, 'Displaced'), (3, 'Oil'), (4, 'Disability'), (5, 'Revolution'), (6, 'Copy'), (7, 'Split')], default=1, verbose_name='type')),
                ('center_lat', models.DecimalField(blank=True, decimal_places=8, max_digits=11, null=True, validators=[django.core.validators.MaxValueValidator(Decimal('90.0')), django.core.validators.MinValueValidator(Decimal('-90.0'))], verbose_name='latitude')),
                ('center_lon', models.DecimalField(blank=True, decimal_places=8, max_digits=11, null=True, validators=[django.core.validators.MaxValueValidator(Decimal('180.0')), django.core.validators.MinValueValidator(Decimal('-180.0'))], verbose_name='longitude')),
                ('reg_open', models.BooleanField(default=True, verbose_name='support for registrations')),
                ('constituency', models.ForeignKey(default=999, on_delete=django.db.models.deletion.CASCADE, to='register.Constituency', verbose_name='constituency')),
                ('copy_of', models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='copied_by', to='register.RegistrationCenter', verbose_name='copy of')),
                ('office', models.ForeignKey(default=999, on_delete=django.db.models.deletion.CASCADE, to='register.Office', verbose_name='office')),
                ('subconstituency', models.ForeignKey(default=999, on_delete=django.db.models.deletion.CASCADE, related_name='registration_centers', to='register.SubConstituency', verbose_name='subconstituency')),
            ],
            options={
                'verbose_name': 'registration center',
                'verbose_name_plural': 'registration centers',
                'ordering': ['center_id'],
                'permissions': (('read_registrationcenter', 'Can view registration center'), ('browse_registrationcenter', 'Can browse registration centers')),
            },
            bases=(libya_elections.libya_bread.ConstituencyFormatterMixin, libya_elections.libya_bread.OfficeFormatterMixin, libya_elections.libya_bread.SubconstituencyFormatterMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Registration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='creation date')),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='modification date')),
                ('archive_time', models.DateTimeField(blank=True, default=None, help_text='If non-NULL, from this time on, this record is no longer in effect.', null=True, verbose_name='archive time')),
                ('change_count', models.IntegerField(default=0, help_text='The number of times this registration has been changed after it was initially made (original registration not counted). ', verbose_name='change count')),
                ('max_changes', models.IntegerField(default=3, help_text='The number of times this registration is allowed to be changed after it was initially made. Defaults to 3, but can be increased.', verbose_name='max changes')),
                ('repeat_count', models.IntegerField(default=1, help_text='The number of times messages have been received for this exact registration. The first message is counted, so the 2nd time we see the same registration, the count becomes 2, and so forth. This is reset each time the registration is changed.', verbose_name='repeat count')),
                ('unlocked_until', models.DateTimeField(blank=True, help_text="If this is set and the current datetime is earlier than this value, allow changing this registration from any phone, even if it's not the phone previously used.", null=True, verbose_name='unlocked until')),
                ('citizen', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='registrations', to='civil_registry.Citizen', verbose_name='citizen')),
                ('registration_center', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='register.RegistrationCenter', verbose_name='registration center')),
                ('sms', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='registrations', to='register.SMS', verbose_name='sms')),
            ],
            options={
                'verbose_name': 'registration',
                'verbose_name_plural': 'registrations',
                'ordering': ['-creation_date'],
                'permissions': (('read_registration', 'Can read registration'), ('browse_registration', 'Can browse registration')),
            },
            bases=(libya_elections.libya_bread.CitizenFormatterMixin, libya_elections.libya_bread.RegistrationCenterFormatterMixin, libya_elections.libya_bread.SMSFormatterMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='creation date')),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='modification date')),
                ('blocked', models.BooleanField(default=False, help_text='Whether this person is blocked from registering and voting', verbose_name='blocked')),
                ('citizen', models.ForeignKey(help_text='Uniquely identifies a person, even across changes of national ID', on_delete=django.db.models.deletion.PROTECT, to='civil_registry.Citizen', verbose_name='citizen')),
            ],
            options={
                'verbose_name': 'person',
                'verbose_name_plural': 'people',
                'ordering': ['id'],
                'permissions': (('read_person', 'Can read person'),),
            },
        ),
    ]
