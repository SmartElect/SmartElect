from datetime import timedelta

from django.conf import settings
from django.utils.timezone import now

from celery.task import task

from audit.models import Discrepancy, SMSTrail, VumiLog
from audit.parser import LogParser
from libya_elections.constants import INCOMING, OUTGOING
from register.models import SMS
from subscriptions.models import Subscription
from subscriptions.utils import send_notifications


def audit_incoming_sms():
    """
    Checks the vumi log model for incoming message against the sms table.
    Vumi logs a message acknowledging a message as soon as it is received from
    the MNOS.
    """
    incoming = VumiLog.objects.filter(is_audited=False, direction=INCOMING)
    discrepancies = []
    for incoming_sms in incoming:
        trail = SMSTrail(vumi=incoming_sms)
        try:
            sms = SMS.objects.get(uuid=incoming_sms.uuid)
        except SMS.DoesNotExist:
            # we do not have record of this incoming message
            sms = None
        else:
            sms.is_audited = True
            sms.save()
        trail.sms = sms
        trail.save()
        if not trail.sms:
            discrepancies.append(Discrepancy.objects.create(trail=trail))
    # sms will not be audited again
    incoming.update(is_audited=True)
    return discrepancies


def audit_outgoing_sms():
    """
    Check the sms table for outgoing message and compare those to the
    message vumi sent to the MNOS.
    """
    # only audit messages older than 24 hours
    time_threshold = now() - timedelta(hours=24)
    outgoing = SMS.objects.filter(is_audited=False, direction=OUTGOING,
                                  creation_date__lt=time_threshold) \
                          .exclude(uuid=None) \
                          .exclude(carrier__name=settings.HTTPTESTER_BACKEND)
    discrepancies = []
    for outgoing_sms in outgoing:
        trail = SMSTrail(sms=outgoing_sms)
        entries = VumiLog.objects.filter(uuid=outgoing_sms.uuid)
        if entries:
            entries.update(is_audited=True)
            vumi_log = entries[0]
        else:
            vumi_log = None
        trail.vumi = vumi_log
        trail.save()
        if not trail.vumi:
            discrepancies.append(Discrepancy.objects.create(trail=trail))
    # sms will not be audited again
    outgoing.update(is_audited=True)
    return discrepancies


@task
def audit_sms():
    discrepancies = audit_incoming_sms()
    discrepancies.extend(audit_outgoing_sms())
    if discrepancies:
        # notify interested parties
        send_notifications(subscription_type=Subscription.DISCREPANCIES,
                           discrepancies=discrepancies)


@task
def parse_logs():
    # parse log for incoming messages
    LogParser(INCOMING).parse()
    # parse log for outgoing messages
    LogParser(OUTGOING).parse()
