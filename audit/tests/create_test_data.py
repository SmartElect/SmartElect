# Python imports
import sys
sys.path.append('.')

# 3rd party imports
from django.conf import settings

# Project imports
from audit.models import Discrepancy, SMSTrail, VumiLog
from audit.tasks import audit_sms
from audit.tests.factories import VumiLogFactory
from help_desk.models import Case
from libya_elections.constants import OUTGOING
from register.models import SMS, Registration
from register.tests.base import PAST_DAY
from register.tests.factories import SMSFactory

DELETE_EXISTING_DATA_ARG = '--yes-delete-my-data'
NUM_INCOMING = NUM_OUTGOING = 10


def create(delete_old_data=False):
    assert settings.ENVIRONMENT not in ('production', 'testing')

    if delete_old_data:
        SMSTrail.objects.unfiltered().delete()
        VumiLog.objects.unfiltered().delete()
        Case.objects.unfiltered().delete()
        Registration.objects.unfiltered().delete()
        SMS.objects.unfiltered().delete()
        Discrepancy.objects.unfiltered().delete()

    for i in range(NUM_INCOMING):
        # create incoming VumiLog instances
        v = VumiLogFactory()

        # create SMS instances for all but 1, so we'll have 1 discrepancy
        if i > 0:
            SMSFactory(
                from_number=v.from_addr,
                to_number=v.to_addr,
                direction=v.direction,
                message=v.content,
                uuid=v.uuid,
            )

    for i in range(NUM_OUTGOING):
        # create outgoing SMS instances (a couple days old, so they'll be audited)
        s = SMSFactory(
            creation_date=PAST_DAY,
            modification_date=PAST_DAY,
            direction=OUTGOING

        )

        # create Vumi instances for all but 1, so we'll have 1 discrepancy
        if i > 0:
            VumiLogFactory(
                from_addr=s.from_number,
                to_addr=s.to_number,
                direction=s.direction,
                content=s.message,
                uuid=s.uuid,
            )

    # run the audit
    audit_sms()
