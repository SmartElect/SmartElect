# Generated by Django 2.2 on 2019-05-03 14:05

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import libya_elections.libya_bread
import libya_elections.phone_numbers


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('register', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Batch',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='creation date')),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='modification date')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('status', models.IntegerField(choices=[(6, 'Uploading'), (1, 'Pending Approval'), (2, 'Approved'), (3, 'Rejected'), (4, 'Completed'), (5, 'Processing')], default=1)),
                ('errors', models.IntegerField(default=0)),
                ('priority', models.IntegerField(default=0, help_text='Batches with higher priority are sent first')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='batches_created', to=settings.AUTH_USER_MODEL)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='batches_reviewed', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'batch',
                'verbose_name_plural': 'batches',
                'ordering': ['-creation_date'],
            },
        ),
        migrations.CreateModel(
            name='BulkMessage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='creation date')),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='modification date')),
                ('phone_number', libya_elections.phone_numbers.PhoneNumberField(max_length=13, verbose_name='phone number')),
                ('from_shortcode', models.CharField(default='10020', help_text='What shortcode should this appear to be from?', max_length=5, verbose_name='from shortcode')),
                ('message', models.TextField(verbose_name='message')),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='bulk_sms.Batch', verbose_name='batch')),
                ('sms', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='register.SMS', verbose_name='sms')),
            ],
            options={
                'verbose_name': 'bulk message',
                'verbose_name_plural': 'bulk messages',
                'ordering': ['-creation_date'],
            },
        ),
        migrations.CreateModel(
            name='Broadcast',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted', models.BooleanField(default=False, verbose_name='deleted')),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='creation date')),
                ('modification_date', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='modification date')),
                ('audience', models.CharField(choices=[('staff', 'Staff'), ('single_center', 'Registrants in a single center'), ('all_centers', 'Registrants in the entire voter register'), ('custom', 'Custom')], default='staff', max_length=20, verbose_name='audience')),
                ('message', models.TextField(verbose_name='message')),
                ('batch', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='bulk_sms.Batch', verbose_name='batch')),
                ('center', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='register.RegistrationCenter', verbose_name='registration center')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='broadcast_created', to=settings.AUTH_USER_MODEL, verbose_name='created by')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='broadcast_reviewed', to=settings.AUTH_USER_MODEL, verbose_name='reviewed by')),
            ],
            options={
                'verbose_name': 'broadcast',
                'verbose_name_plural': 'broadcasts',
                'ordering': ['creation_date'],
                'permissions': (('approve_broadcast', 'Can approve broadcast messages'), ('read_broadcast', 'Can view broadcast messages'), ('browse_broadcast', 'Can browse broadcast messages')),
            },
            bases=(libya_elections.libya_bread.CreatedByFormatterMixin, libya_elections.libya_bread.RegistrationCenterFormatterMixin, libya_elections.libya_bread.ReviewedByFormatterMixin, models.Model),
        ),
    ]