import datetime
from optparse import make_option

from django.db import transaction
from django.core.management.base import BaseCommand
from libya_elections.constants import INCOMING, OUTGOING

from register.models import SMS


class Command(BaseCommand):
    help = """
    Try to find the incoming SMS corresponding to every outgoing SMS and then:
        1. Set outgoing SMS's in_response_to to point to the incoming SMS
        2. Set incoming SMS's message_code to be equal to outgoing's message_code

    We ignore bulk_sms messages which are one-way outgoing messages. Those, at the time this
    management command was written, have a from_number of 'HNEC'. We also ignore any messages
    with from_number or to_number of 218888888888 or 218999999999 as those messages were created
    in ad-hoc queries and weren't true SMS messages that travelled through our system.
    """

    option_list = BaseCommand.option_list + (
        make_option(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            default=False,
            help="Dry run, don't actually execute database update"),
        )

    @transaction.commit_manually
    def handle(self, *args, **options):
        outgoing_sms_qs = SMS.objects.filter(
            direction=OUTGOING,
            # only care about messages after registration started
            creation_date__gt=datetime.date(2013, 11, 30),
            # don't change messages that are already properly linked
            in_response_to=None,
        ).exclude(
            # exclude bulk messages, and messages created by ad-hoc queries
            from_number__in=('HNEC', '218888888888', '218999999999'),
        ).exclude(
            to_number__in=('218888888888', '218999999999'),
        )

        linked = not_linked = 0
        for i, outgoing_sms in enumerate(outgoing_sms_qs):
            # progress marker every 100,000 messages
            if i and i % 100000 == 0:
                transaction.commit()
                if options['dry_run']:
                    print('Would have linked %d of %d messages' % (linked, i))
                else:
                    print('Successfully linked %d of %d messages' % (linked, i))

            try:
                # find the latest incoming sms that matches
                incoming_sms_qs = SMS.objects.filter(
                    direction=INCOMING,
                    from_number=outgoing_sms.to_number,
                    to_number=outgoing_sms.from_number,
                    msg_type=outgoing_sms.msg_type,
                    # all incoming messages currently have message_code=0
                    # if it doesn't, then it has already been updated, so skip it
                    message_code=0,
                    creation_date__lte=outgoing_sms.creation_date,
                ).order_by('-creation_date')

                if incoming_sms_qs:
                    linked += 1
                    if not options['dry_run']:
                        incoming_sms = incoming_sms_qs[0]
                        incoming_sms.message_code = outgoing_sms.message_code
                        incoming_sms.save()
                        outgoing_sms.in_response_to = incoming_sms
                        outgoing_sms.save()
                else:
                    not_linked += 1
            except KeyboardInterrupt:
                print('\n\nKeyboardInterrupt handled...')
                # break the loop and skip to the commit statement below
                break

        transaction.commit()
        print('FINAL RESULTS:')
        if options['dry_run']:
            print("DB was not changed, but this is what we would have done.")
        print('Successfully linked to an incoming SMS: %d' % linked)
        print('Could not identify the incoming SMS: %d' % not_linked)
