import logging

from celery.task import task

from rollgen.utils import handle_job_exception


logger = logging.getLogger('rollgen')


@task
def run_roll_generator_job(job):
    """Run the rollgen job.

    If an exception occurs, write exception info to failure info file so the Web process can
    read it.
    """
    try:
        job.generate_rolls()
    except Exception as exception:
        is_expected = handle_job_exception(exception, job.output_path)

        if not is_expected:
            logger.exception("Error executing job")
