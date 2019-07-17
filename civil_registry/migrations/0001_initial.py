# Generated by Django 2.2 on 2019-05-03 14:05

import civil_registry.models
from django.db import migrations, models
import libya_elections.libya_bread


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Citizen',
            fields=[
                ('civil_registry_id', models.BigIntegerField(help_text='Uniquely identifies a person, even across changes of national ID', primary_key=True, serialize=False, verbose_name='civil registry id')),
                ('national_id', models.BigIntegerField(db_index=True, help_text="The citizen's 12-digit national ID number", unique=True, validators=[civil_registry.models.national_id_validator], verbose_name='national id')),
                ('fbr_number', models.CharField(help_text='Family Book Record Number', max_length=20, validators=[civil_registry.models.fbr_number_validator], verbose_name='family book record number')),
                ('first_name', models.CharField(blank=True, db_index=True, max_length=255, verbose_name='first name')),
                ('father_name', models.CharField(blank=True, max_length=255, verbose_name='father name')),
                ('grandfather_name', models.CharField(blank=True, max_length=255, verbose_name='grandfather name')),
                ('family_name', models.CharField(blank=True, db_index=True, max_length=255, verbose_name='family name')),
                ('mother_name', models.CharField(blank=True, max_length=255, verbose_name='mother name')),
                ('birth_date', models.DateField(db_index=True, verbose_name='birth date')),
                ('gender', models.IntegerField(choices=[(2, 'Female'), (1, 'Male')], db_index=True, verbose_name='gender')),
                ('address', models.CharField(blank=True, max_length=1024, verbose_name='address')),
                ('office_id', models.IntegerField(default=0, verbose_name='office id')),
                ('branch_id', models.IntegerField(default=0, verbose_name='branch id')),
                ('state', models.IntegerField(default=0, verbose_name='state')),
                ('missing', models.DateTimeField(blank=True, help_text='If set, this citizen was not in the last data dump.', null=True, verbose_name='missing')),
            ],
            options={
                'verbose_name': 'citizen',
                'verbose_name_plural': 'citizens',
                'ordering': ['national_id'],
                'permissions': (('read_citizen', 'Can read citizens'), ('browse_citizen', 'Can browse citizens')),
            },
            bases=(libya_elections.libya_bread.BirthDateFormatterMixin, models.Model),
        ),
        migrations.CreateModel(
            name='CitizenMetadata',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dump_time', models.DateTimeField()),
            ],
        ),
        migrations.CreateModel(
            name='DumpFile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('filename', models.CharField(max_length=256)),
            ],
        ),
        migrations.CreateModel(
            name='TempCitizen',
            fields=[
                ('civil_registry_id', models.BigIntegerField(help_text='Uniquely identifies a person, even across changes of national ID', primary_key=True, serialize=False, verbose_name='civil registry id')),
                ('national_id', models.BigIntegerField(db_index=True, help_text="The citizen's 12-digit national ID number", unique=True, validators=[civil_registry.models.national_id_validator], verbose_name='national id')),
                ('fbr_number', models.CharField(help_text='Family Book Record Number', max_length=20, validators=[civil_registry.models.fbr_number_validator], verbose_name='family book record number')),
                ('first_name', models.CharField(blank=True, db_index=True, max_length=255, verbose_name='first name')),
                ('father_name', models.CharField(blank=True, max_length=255, verbose_name='father name')),
                ('grandfather_name', models.CharField(blank=True, max_length=255, verbose_name='grandfather name')),
                ('family_name', models.CharField(blank=True, db_index=True, max_length=255, verbose_name='family name')),
                ('mother_name', models.CharField(blank=True, max_length=255, verbose_name='mother name')),
                ('birth_date', models.DateField(db_index=True, verbose_name='birth date')),
                ('gender', models.IntegerField(choices=[(2, 'Female'), (1, 'Male')], db_index=True, verbose_name='gender')),
                ('address', models.CharField(blank=True, max_length=1024, verbose_name='address')),
                ('office_id', models.IntegerField(default=0, verbose_name='office id')),
                ('branch_id', models.IntegerField(default=0, verbose_name='branch id')),
                ('state', models.IntegerField(default=0, verbose_name='state')),
                ('missing', models.DateTimeField(blank=True, help_text='If set, this citizen was not in the last data dump.', null=True, verbose_name='missing')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
