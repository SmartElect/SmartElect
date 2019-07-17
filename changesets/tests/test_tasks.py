from unittest.mock import patch

from django.test import TestCase

from changesets.models import Changeset
from changesets.tasks import execute_changeset
from changesets.tests.factories import ChangesetFactory


class TasksTest(TestCase):
    def test_no_such_changeset(self):
        # Call task with pk for no such changeset
        # should log an error
        with patch('changesets.tasks.logger') as mock_logger:
            execute_changeset(9999)
        assert mock_logger.error.called

    def test_execute_raises_exception(self):
        # If execute raises exception, it is logged
        changeset = ChangesetFactory()
        with patch('changesets.tasks.logger') as mock_logger:
            with patch.object(Changeset, 'execute') as mock_execute:
                mock_execute.side_effect = ValueError
                execute_changeset(changeset.pk)
        assert mock_logger.exception.called

    def test_task_calls_execute(self):
        # task calls execute
        # seems kind of pointless, but might as well be complete
        changeset = ChangesetFactory()
        with patch.object(Changeset, 'execute') as mock_execute:
            execute_changeset(changeset.pk)
        assert mock_execute.called
