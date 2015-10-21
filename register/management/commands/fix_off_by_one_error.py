from django.core.management.base import BaseCommand
from register.models import RegistrationCenter


class Command(BaseCommand):
    help = 'Fix off by one names caused by an error in the original spreadsheet'

    def handle(self, *args, **options):
        start_id = 14095
        end_id = 14151

        first_wrong_center = RegistrationCenter.objects.get(center_id=start_id)
        last_correct_center = RegistrationCenter.objects.get(center_id=start_id - 1)

        if first_wrong_center.name == last_correct_center.name:
            print "off by one issue detected, fixing"
        else:
            print "off by one issue not detected, exiting"
            return

        num_fixed = 0
        for center_id in range(start_id, end_id + 1):
            center = RegistrationCenter.objects.get(center_id=center_id)
            next_center = RegistrationCenter.objects.get(center_id=center_id + 1)

            center.name = next_center.name

            # flag last center to fix manually
            if center_id == end_id:
                center.name = "FIX ME MANUALLY"
            center.save()
            num_fixed += 1
        print "fixed %d centers" % num_fixed
