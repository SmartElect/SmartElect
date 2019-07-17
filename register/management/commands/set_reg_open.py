from django.core.management.base import BaseCommand, CommandError

from register.models import RegistrationCenter


class Command(BaseCommand):
    help = """
    Set the reg_open parameter for 1 or more subconstituencies.

    Open all centers:
      set_reg_open --all

    Close all centers:
      set_reg_open --false --all

    Open centers in subcon 5:
      set_reg_open 5

    Close centers in subcons 2 and 8:
      set_reg_open --false 2 8

    Note: --all cannot be provided along with subcons. They are mutually exclusive
    """

    def add_arguments(self, parser):
        parser.add_argument('subcon_id', nargs='*', type=int)
        parser.add_argument(
            '--all',
            action='store_true',
            dest='all',
            default=False,
            help='Set for all centers')
        parser.add_argument(
            '--false',
            action='store_false',
            dest='reg_open',
            default=True,  # default reg_open to True
            help='Set reg_open to False')

    def handle(self, *args, **options):
        reg_open = options['reg_open']
        subcon_list = options['subcon_id']

        if options['all'] and subcon_list:
            raise CommandError('Choose either --all or provide a list of subcons, not both.')

        if options['all']:
            centers = RegistrationCenter.objects.all()
        elif subcon_list:
            centers = RegistrationCenter.objects.filter(subconstituency_id__in=subcon_list)
        else:
            raise CommandError('Neither --all nor subcon_ids were provided.')
        updated = centers.update(reg_open=reg_open)
        self.stdout.write('%d centers updated to reg_open=%s.' % (updated, reg_open))
