# -*- coding: utf-8 -*-
from django.db import models, migrations
from libya_elections.constants import SPLIT_CENTER_SUBCONSTITUENCY_ID


from libya_elections.constants import NO_NAMEDTHING


def create_no_namedthing_objects(apps, schema_editor):
    Office = apps.get_model("register", "Office")
    no_office, _ = Office.objects.get_or_create(
        id=NO_NAMEDTHING,
        defaults={
            'name_english': 'No Office',
            'name_arabic': 'من غير اللجنة الانتخابية',
        }
    )

    Constituency = apps.get_model("register", "Constituency")
    no_con, _ = Constituency.objects.get_or_create(
        id=NO_NAMEDTHING,
        defaults={
            'name_english': 'No Constituency',
            'name_arabic': 'من غير الدائرة الانتخابية الرئيسية',
        }
    )

    SubConstituency = apps.get_model("register", "SubConstituency")
    no_subcon, _ = SubConstituency.objects.get_or_create(
        id=NO_NAMEDTHING,
        defaults={
            'name_english': 'No Subconstituency',
            'name_arabic': 'من غير الدائرة الفرعية',
        }
    )


def no_op(apps, schema_editor):
    pass


def create_split_center_subconstituency(apps, schema_editor):
    SubConstituency = apps.get_model("register", "SubConstituency")
    SubConstituency.objects.get_or_create(
        id=SPLIT_CENTER_SUBCONSTITUENCY_ID,
        defaults={
            'name_english': 'Split Center Subconstituency',
            'name_arabic': 'مركز انقسام الفرعية',
        }
    )


class Migration(migrations.Migration):

    dependencies = [
        ('register', '0002_add_indices'),
    ]

    operations = [
        migrations.RunPython(create_split_center_subconstituency, reverse_code=no_op),
        migrations.RunPython(create_no_namedthing_objects, reverse_code=no_op),
    ]
