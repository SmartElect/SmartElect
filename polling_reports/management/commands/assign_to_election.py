from collections import defaultdict
from datetime import timedelta
from optparse import make_option

from django.core.management import BaseCommand

from polling_reports.models import CenterOpen, PollingReport
from voting.models import Election

OLD_ELECTIONS = ['Constitutional Drafting Assembly Election',
                 'CDA (Additional Polling Day)']


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--assign', action='store_true',
                    help='Change the database (default is to only report unassignable messages)'),
    )

    def handle(self, *args, **options):
        return self.assign_to_election(update=options['assign'])

    @classmethod
    def handle_message(cls, elections, update, message, unassigned):
        """ returns 1 if a message is modified in the db, 0 otherwise """
        found = False
        for e in elections:
            # work_{start|end}_time is supposed to cover the range of times where
            # messages are expected, but in the past some messages have fallen
            # outside of that window; expand by some fuzz in either direction
            # (tailored to specific issues seen)
            election_earliest, election_latest = (
                e.work_start_time - timedelta(days=2),
                e.work_end_time + timedelta(days=1, hours=12),
            )
            if election_earliest <= message.creation_date <= election_latest:
                found = True
                if update:
                    message.election = e
                    if e.name_english in OLD_ELECTIONS:
                        message.deleted = False
                    message.save()
                    return 1
                break
        if not found:
            unassigned.append(message)
        return 0

    def assign_to_election(self, update=False):
        elections = Election.objects.all()
        # messages for which an election wasn't found
        unassigned_center_open_messages = []
        unassigned_polling_report_messages = []
        total_messages = total_messages_modified = total_messages_already_assigned = 0

        queryset = CenterOpen.objects.unfiltered()
        total_messages += queryset.count()
        total_messages_already_assigned += queryset.exclude(election=None).count()
        queryset = queryset.filter(election=None)
        for center_open in queryset:
            total_messages_modified += \
                self.handle_message(elections, update, center_open,
                                    unassigned_center_open_messages)

        queryset = PollingReport.objects.unfiltered()
        total_messages += queryset.count()
        total_messages_already_assigned += queryset.exclude(election=None).count()
        queryset = queryset.filter(election=None)
        for polling_report in queryset:
            total_messages_modified += \
                self.handle_message(elections, update, polling_report,
                                    unassigned_polling_report_messages)

        self.stdout.write('Known elections:')
        for election in elections:
            self.stdout.write('  %s (%s) from %s to %s' % (
                election.name_arabic, election.name_english,
                election.work_start_time, election.work_end_time))
        self.stdout.write('')
        if unassigned_center_open_messages:
            self.stdout.write('Synopsis of center open messages which do not match an '
                              'election:')
            counts_by_date = defaultdict(int)
            for unassigned in unassigned_center_open_messages:
                counts_by_date[unassigned.creation_date.date()] += 1
            self.stdout.write('  %-20s      Count' % 'Date')
            self.stdout.write('  %-20s      -----' % ('-' * 20))
            for k in sorted(counts_by_date.keys()):
                self.stdout.write('  %-20s % 10d' % (k, counts_by_date[k]))
            self.stdout.write('')

        if unassigned_polling_report_messages:
            self.stdout.write('Polling report messages which do not match an election:')
            for unassigned in unassigned_polling_report_messages:
                self.stdout.write('  %s from %s, created at %s' % (
                    unassigned, unassigned.phone_number, unassigned.creation_date
                ))
            self.stdout.write('')

        self.stdout.write('Total messages processed:                   % 10d' %
                          total_messages)
        self.stdout.write('Total messages previously assigned:         % 10d' %
                          total_messages_already_assigned)
        self.stdout.write('Total unassignable center open messages:    % 10d' %
                          len(unassigned_center_open_messages))
        self.stdout.write('Total unassignable polling report messages: % 10d' %
                          len(unassigned_polling_report_messages))
        self.stdout.write('Total messages modified:                    % 10d' %
                          total_messages_modified)
        self.stdout.write('  (database updates %s)'
                          % ('enabled' if update else 'disabled'))
