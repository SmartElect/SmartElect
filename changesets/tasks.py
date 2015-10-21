import logging
from celery.task import task

from changesets.models import Changeset


logger = logging.getLogger(__name__)


@task
def execute_changeset(changeset_pk):
    try:
        changeset = Changeset.objects.get(pk=changeset_pk)
    except Changeset.DoesNotExist:
        logger.error("No changeset with pk=%s", changeset_pk)
    else:
        try:
            changeset.execute()
        except Exception:
            # Catch any exception, to make sure it gets logged
            logger.exception("Error executing changeset %s", changeset)
