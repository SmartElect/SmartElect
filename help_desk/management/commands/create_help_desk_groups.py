from django.core.management.base import NoArgsCommand
from help_desk.utils import create_help_desk_groups


class Command(NoArgsCommand):
    args = '(no args)'
    help = 'Creates any missing Help Desk Groups and Permissions'

    def handle_noargs(self, **options):
        create_help_desk_groups()
        self.stdout.write("Successfully created any missing Help Desk permissions and groups")
