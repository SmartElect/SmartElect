import logging

from celery.task import task, Task
from django.conf import settings

from .reports import generate_registrations_reports, \
    generate_election_day_reports_and_logs

logger = logging.getLogger(__name__)


class LoggedTask(Task):
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error('Error in task: %s' % exc)
        logger.error(str(einfo))


@task(base=LoggedTask)
def registrations():
    generate_registrations_reports()


@task(base=LoggedTask)
def election_day():
    generate_election_day_reports_and_logs()


def schedule_reporting_api_tasks(schedule, intervals):
    """ Process REPORT_GENERATION_INTERVALS defined in settings (or some alternative
    for testing), to schedule the tasks to maintain the various reports.
    """
    tasks = ('registrations', 'election_day')
    for task_name in tasks:
        if task_name in intervals:
            delta = intervals[task_name]
        elif 'default' in intervals:
            delta = intervals['default']
        else:
            logger.error('Task %s won\'t be scheduled -- no interval defined in settings')
            continue
        # The task will expire if it has not been completed in 75% of the delta (a
        # task that is set to run every 30 minutes will expire after 1350 seconds).
        expire_duration = (delta.days * 24 * 60 * 60 + delta.seconds) * 0.75
        schedule.update({'generate-%s' % task_name: {
            'task': 'reporting_api.tasks.%s' % task_name,
            'schedule': delta,
            'options': {
                'expires': expire_duration
            }
        }})


if settings.REPORT_GENERATION_INTERVALS:
    schedule_reporting_api_tasks(settings.CELERY_BEAT_SCHEDULE,
                                 settings.REPORT_GENERATION_INTERVALS)
