from django.core.management.base import BaseCommand, CommandError
from django.db.models import F

from register.models import Registration


class Command(BaseCommand):
    help = """
    Set the remaining_changes parameter for registrants at 1 or more subconstituencies.

    Set to zero remaining changes for all centers:
      set_remaining_changes --zero --all

    Set to one remaining change for subcons 2 and 8:
      set_remaining_changes --one 2 8

    Set to the max amount of remaining changes for subcon 5:
      set_remaining_changes --max 5

    Note: --all cannot be provided along with subcons. They are mutually exclusive
    """

    def add_arguments(self, parser):
        parser.add_argument('subcon_id', nargs='*', type=int)
        parser.add_argument(
            '--all',
            action='store_true',
            dest='all',
            default=False,
            help='Set for all registrations')
        parser.add_argument(
            '--zero',
            action='store_const',
            dest='remaining',
            const=0,
            help='Allow no more changes')
        parser.add_argument(
            '--one',
            action='store_const',
            dest='remaining',
            const=1,
            help='Allow one more change')
        parser.add_argument(
            '--max',
            action='store_const',
            dest='remaining',
            const=-1,
            help='Allow the max amount of changes')

    def handle(self, *args, **options):
        remaining = options['remaining']
        subcon_list = options['subcon_id']

        if options['all'] and subcon_list:
            raise CommandError('Choose either --all or provide a list of subcons, not both.')

        if options['all']:
            registrations = Registration.objects.all()
        elif subcon_list:
            registrations = Registration.objects.filter(
                registration_center__subconstituency_id__in=subcon_list)
        else:
            raise CommandError('Neither --all nor subcon_ids were provided.')

        if remaining == -1:  # allow max changes
            updated = registrations.update(change_count=0)
        elif remaining in [0, 1]:
            updated = registrations.update(change_count=F('max_changes') - remaining)
        else:
            raise CommandError('Provide --zero, --one, or --max to specify # of changes allowed.')
        self.stdout.write('%d registrations updated.' % updated)
