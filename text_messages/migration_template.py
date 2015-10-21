# -*- coding: utf-8 -*-

# THIS IS A TEMPLATE FOR MIGRATIONS TO CREATE NEW MESSAGES
# SEE docs/sms_responses.rst for more about what this is for.

from __future__ import unicode_literals

from django.db import migrations

from text_messages.utils import maybe_add_message_to_database


def no_op(apps, schema_editor):
    # No need for a reverse migration
    pass


def add_message(apps, schema_editor):
    MessageText = apps.get_model("text_messages", "MessageText")

    maybe_add_message_to_database(
        MessageText,  # Don't change this
        number=0,  # FILL THESE IN WITH THE DATA FOR THE NEW MESSAGE
        label='',
        msg_en='',
        msg_ar='',
        enhanced_en='',
        enhanced_ar=''
    )
    # Add more calls to maybe_add_message_to_database as needed
    # to add more messages.


class Migration(migrations.Migration):

    dependencies = [
        # CHANGE THE NEXT LINE:
        ('text_messages', 'REPLACE_WITH_HIGHEST_CURRENT_MIGRATION'),
    ]

    operations = [
        migrations.RunPython(
            add_message,
            no_op,
        )
    ]
