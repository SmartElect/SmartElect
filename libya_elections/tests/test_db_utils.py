# coding: utf-8
from django.test import TestCase
from django.test.utils import override_settings
from mock import MagicMock, patch

from libya_elections.db_utils import delete_all, BatchOperations
from civil_registry.models import Citizen
from register.models import Whitelist
from register.tests.factories import WhitelistFactory


class DBCollationTest(TestCase):
    """
    Verify that our database is using LC_COLLATE=en_US.UTF-8

    (Not directly related to db_utils.py, but the test has to go somewhere.)
    """
    def test_collate_setting(self):
        from django.db import connection

        cursor = connection.cursor()
        cursor.execute("show LC_COLLATE")
        rows = cursor.fetchall()
        setting = rows[0][0]
        self.assertEqual('en_US.UTF-8', setting)


class DeleteAllTest(TestCase):
    def setUp(self):
        self.db = 'default'

    def test_simple_delete(self):
        # Nothing in the test database?
        # (Need to use a model that has no foreign keys pointing at it.
        # Otherwise, doesn't matter which model.)
        model = Whitelist
        factory = WhitelistFactory
        self.assertFalse(model.objects.exists())
        # Add something
        factory()
        self.assertTrue(model.objects.exists())
        delete_all(self.db, [model])
        self.assertFalse(model.objects.exists())

    def test_cascade(self):
        # Mentioning cascade adds it to the command
        mock_cursor = MagicMock()
        with patch('libya_elections.db_utils.get_cursor') as mock_get_cursor:
            mock_get_cursor.return_value = mock_cursor
            delete_all(self.db, [Citizen], cascade=True)
        expected_cmd = "TRUNCATE civil_registry_citizen CASCADE"
        mock_cursor.execute.assert_called_with(expected_cmd)

    def test_postgres_only(self):
        # If db is not postgres, raises exception
        # Note that overriding DATABASES in a test triggers
        # a warning, but I think since we're not actually doing anything
        # in the database while we have it overridden, it's okay.
        # (The code under test just inspects the setting and returns.)
        DATABASES = {
            self.db: {
                'ENGINE': 'elcheaposqldb',
            }
        }
        with override_settings(DATABASES=DATABASES):
            with self.assertRaises(NotImplementedError):
                delete_all(self.db, [])


class BatchAddTest(TestCase):
    def test_add_one_record(self):
        # Calling it once should just add the data to the list
        # (we don't test what's in the list, that's an implementation detail,
        # just that its length is correct)
        batch = BatchOperations(None)
        data = {'civil_registry_id': 1}
        batch.add(data)
        batch.add(data)
        # There's now something in the list
        self.assertEqual(2, batch.num_pending_adds)

    def test_add_then_flush(self):
        # can add in one call, flush in another
        model = MagicMock()
        data = {'a': 1}
        batch = BatchOperations(model)
        batch.add(data)
        self.assertEqual(1, batch.num_pending_adds)
        batch.flush()
        self.assertEqual(0, batch.num_pending_adds)
        model.objects.bulk_create.assert_called_with([model(**data)])


class BatchDeleteTest(TestCase):
    def test_delete_one_record(self):
        batch = BatchOperations(None)
        pk = 1
        batch.delete(pk)
        self.assertEqual(1, batch.num_pending_deletes)

    def test_delete_then_flush(self):
        pk = 1
        model = MagicMock()

        # The utility ought to call model.objects.filter(pk__in=[pk]).delete().
        # Use side_effect to get mock to call our code when it
        # tries to call objects.filter, so that we can check that
        # it passed the expected args, pk__in=[pk].
        # Then return another mock, which the caller should try to
        # call delete() on, so we can check that too.
        filter_return = MagicMock()

        def our_callback(*args, **kwargs):
            assert not args
            assert kwargs == {'pk__in': [pk]}
            return filter_return

        model = MagicMock(side_effect=our_callback)
        batch = BatchOperations(model)
        batch.delete(pk)
        batch.flush()
        filter_return.delete.assert_called()
