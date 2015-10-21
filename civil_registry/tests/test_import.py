# coding: utf-8
from datetime import timedelta
from time import sleep

from django.forms import model_to_dict
from django.test import TestCase
from django.utils.timezone import now
from mock import patch, ANY

from civil_registry.models import Citizen, TempCitizen, CitizenMetadata
from civil_registry.tests.factories import CitizenFactory
from civil_registry.utils import import_citizen_dump, TooManyChanges
from libya_elections.db_mirror import MirrorStats
from libya_elections.db_utils import delete_all
from libya_elections.utils import refresh_model


@patch('codecs.open')
@patch('civil_registry.utils.get_records')
class CitizenImportTest(TestCase):
    def setUp(self):
        delete_all('default', [Citizen, TempCitizen, CitizenMetadata], cascade=True)

    def test_metadata_created(self, get_records, open):
        get_records.return_value = []
        with patch('civil_registry.utils.mirror_database') as mirror_database:
            mirror_database.return_value = MirrorStats()
            import_citizen_dump(input_filename=None)
        mirror_database.assert_called()
        self.assertEqual(1, CitizenMetadata.objects.count())

    def test_metadata_updated(self, get_records, open):
        start_time = now()
        last_time = start_time - timedelta(days=2)
        CitizenMetadata.objects.create(dump_time=last_time)
        get_records.return_value = []
        sleep(0.001)  # ensure the clock has advanced very slightly
        with patch('civil_registry.utils.mirror_database') as mirror_database:
            mirror_database.return_value = MirrorStats()
            import_citizen_dump(input_filename=None)
        sleep(0.001)
        meta = CitizenMetadata.objects.get()
        self.assertNotEqual(last_time, meta.dump_time)
        self.assertTrue(meta.dump_time > last_time)
        self.assertTrue(meta.dump_time > start_time)
        self.assertTrue(meta.dump_time < now())

    def test_temp_citizen_created(self, get_records, open):
        citizen = CitizenFactory()
        data = model_to_dict(citizen)
        citizen.delete()
        get_records.return_value = [data]
        self.assertFalse(Citizen.objects.exists())
        self.assertFalse(TempCitizen.objects.exists())
        with patch('civil_registry.utils.delete_all'):
            with patch('civil_registry.utils.mirror_database') as mirror_database:
                mirror_database.return_value = MirrorStats()
                stats = import_citizen_dump(input_filename=None)
        # We mocked mirror_database, so nothing actually got copied to Citizen
        # but it should have "read" the data into TempCitizen, and we
        # mocked delete_all, so it should still be there.
        self.assertFalse(Citizen.objects.exists())
        self.assertEqual(1, stats.records_read)
        mirror_database.assert_called()
        temp_cit = TempCitizen.objects.get()
        self.assertEqual(data, model_to_dict(temp_cit))

    def test_citizen_created(self, get_records, open):
        citizen = CitizenFactory()
        data = model_to_dict(citizen)
        citizen.delete()
        get_records.return_value = [data]
        self.assertFalse(Citizen.objects.exists())
        stats = import_citizen_dump(input_filename=None)
        self.assertEqual(1, stats.records_read)
        new_cit = Citizen.objects.get()
        self.assertEqual(data, model_to_dict(new_cit))

    def test_citizen_updated(self, get_records, open):
        cit1 = CitizenFactory()
        cit2 = CitizenFactory()
        citizen = CitizenFactory()
        data = model_to_dict(citizen)
        new_name = 'Jim Bob'
        data['first_name'] = new_name
        get_records.return_value = [model_to_dict(cit1), model_to_dict(cit2), data]
        stats = import_citizen_dump(input_filename=None, max_change_percent=34)
        self.assertEqual(3, stats.records_read)
        updated_cit = Citizen.objects.get(pk=citizen.pk)
        self.assertEqual(new_name, updated_cit.first_name)

    def test_citizen_missing(self, get_records, open):
        # Citizen in db but not in import
        citizen = CitizenFactory()
        get_records.return_value = []
        stats = import_citizen_dump(input_filename=None, max_change_percent=100)
        self.assertEqual(0, stats.records_read)
        # The record is still there
        self.assertEqual(0, Citizen.objects.count())  # we don't see missing records by default
        self.assertEqual(1, Citizen.objects.unfiltered().count())  # but it's really there
        self.assertEqual(1, stats.not_there_anymore_count)
        self.assertIn(citizen.pk, stats.missing_pks)
        # But it's been marked missing
        citizen = Citizen.objects.unfiltered().get(pk=citizen.pk)
        self.assertTrue(citizen.missing)

    def test_input_filename(self, get_records, open):
        filename = 'my_dump_file'
        import_citizen_dump(input_filename=filename)
        open.assert_called_with(filename, encoding=ANY)

    def test_encoding(self, get_records, open):
        encoding = 'ASCII'
        import_citizen_dump(input_filename=None, encoding=encoding)
        open.assert_called_with(ANY, encoding=encoding)

    def test_too_many_changes(self, get_records, open):
        cit1 = CitizenFactory()
        cit2 = CitizenFactory()
        citizen = CitizenFactory()
        data = model_to_dict(citizen)
        new_name = 'Jim Bob'
        data['first_name'] = new_name
        get_records.return_value = [model_to_dict(cit1), model_to_dict(cit2), data]
        # Import raises an exception:
        with self.assertRaises(TooManyChanges):
            import_citizen_dump(input_filename=None, max_change_percent=10)
        # Citizen is unchanged:
        new_citizen = refresh_model(citizen)
        self.assertEqual(citizen.first_name, new_citizen.first_name)
