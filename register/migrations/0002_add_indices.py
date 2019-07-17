# -*- coding: utf-8 -*-
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('register', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            # Registrations are unique on citizen if archive_time is NULL
            """
            CREATE UNIQUE INDEX unique_registrations ON register_registration (citizen_id) WHERE (archive_time IS NULL AND deleted=FALSE);
            """,
            """
            DROP INDEX IF EXISTS unique_registrations;
            """
        ),
        migrations.RunSQL(
            # We hand-create this index since it's awkward to do via Django
            """
            CREATE INDEX
                register_sms_creation_date_index
            ON
                register_sms (creation_date)
            """,
            """
            DROP INDEX IF EXISTS register_sms_creation_date_index;
            """
        ),
    ]
