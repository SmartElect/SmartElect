import logging
from datetime import timedelta

from django.utils.timezone import now

from celery.task import task

from voting.models import Election


logger = logging.getLogger(__name__)


@task
def poll_for_reminders_to_send():
    """
    If any elections have due unsent reminders,
    send them.
    """
    # We run this every minute on test and production servers.
    # So this isn't too crazy, limit to elections that started within
    # the last week and will end within the next week.
    time_now = now()
    nearby_elections = Election.objects.filter(
        start_time__gte=time_now - timedelta(days=7),
        end_time__lte=time_now + timedelta(days=7)
    )

    # If election times change, make sure we don't suddenly send out all the reminders
    # that we missed a long time ago, by limiting to reminders that are due +/- 5 minutes
    # from now. This will tend to queue up reminders 4-5 minutes before they're due to
    # be sent if all is well, but will provide some redundancy in case the task doesn't
    # run every time it should.
    for election in nearby_elections:
        election.schedule_due_reminders(
            from_time=time_now - timedelta(minutes=5),
            to_time=time_now + timedelta(minutes=5),
        )
