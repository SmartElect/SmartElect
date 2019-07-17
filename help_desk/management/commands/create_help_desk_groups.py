from django.core.management.base import BaseCommand
from help_desk.utils import create_help_desk_groups


class Command(BaseCommand):
    help = 'Creates any missing Help Desk Groups and Permissions'

    def handle(self, *args, **options):
        create_help_desk_groups()
        self.stdout.write("Successfully created any missing Help Desk permissions and groups")
