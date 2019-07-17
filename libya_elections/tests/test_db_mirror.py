from django.forms import model_to_dict
from django.test import TestCase
from django.utils.timezone import now

from civil_registry.models import Citizen, TempCitizen
from civil_registry.tests.factories import TempCitizenFactory, CitizenFactory
from libya_elections.db_mirror import mirror_database
from libya_elections.db_utils import delete_all


class DbMirrorTest(TestCase):
    def setUp(self):
        # We'll use Citizen and TempCitizen. Start with them empty
        # so each test can set them up as desired.
        delete_all('default', [Citizen, TempCitizen], cascade=True)

    def test_empty_dbs(self):
        stats = mirror_database(
            from_model=TempCitizen,
            to_model=Citizen
        )
        self.assertEqual(0, stats.unchanged_count)
        self.assertEqual(0, stats.modified_record_count)
        self.assertEqual(0, stats.new_record_count)
        self.assertEqual(0, stats.not_there_anymore_count)

    def test_new_record(self):
        cit = TempCitizenFactory()
        stats = mirror_database(
            from_model=TempCitizen,
            to_model=Citizen
        )
        self.assertEqual(0, stats.unchanged_count)
        self.assertEqual(0, stats.modified_record_count)
        self.assertEqual(1, stats.new_record_count)
        self.assertEqual(0, stats.not_there_anymore_count)
        self.assertTrue(Citizen.objects.filter(pk=cit.pk).exists())

    def test_new_record_with_existing(self):
        nid = 100000000000
        existing = CitizenFactory(pk=1, national_id=nid)
        TempCitizenFactory(pk=1, **model_to_dict(existing))
        nid += 1
        cit = TempCitizenFactory(pk=2, national_id=nid)
        nid += 1
        existing2 = CitizenFactory(pk=3, national_id=nid)
        TempCitizenFactory(pk=3, **model_to_dict(existing2))
        stats = mirror_database(
            from_model=TempCitizen,
            to_model=Citizen
        )
        self.assertEqual(2, stats.unchanged_count)
        self.assertEqual(0, stats.modified_record_count)
        self.assertEqual(1, stats.new_record_count)
        self.assertEqual(0, stats.not_there_anymore_count)
        self.assertTrue(Citizen.objects.filter(pk=cit.pk).exists())

    def test_changed_record(self):
        cit = CitizenFactory()
        temp_cit = TempCitizenFactory(pk=cit.pk, first_name=cit.first_name + '_CHANGED')
        stats = mirror_database(
            from_model=TempCitizen,
            to_model=Citizen
        )
        self.assertEqual(0, stats.unchanged_count)
        self.assertEqual(1, stats.modified_record_count)
        self.assertEqual(0, stats.new_record_count)
        self.assertEqual(0, stats.not_there_anymore_count)
        c = Citizen.objects.get(pk=cit.pk)
        self.assertEqual(temp_cit.first_name, c.first_name)

    def test_changed_record_with_existing(self):
        nid = 100000000000
        existing = CitizenFactory(pk=1, national_id=nid)
        nid += 1
        TempCitizenFactory(pk=existing.pk, **model_to_dict(existing))
        nid += 1
        cit = CitizenFactory(pk=2, national_id=nid)
        temp_cit = TempCitizenFactory(pk=cit.pk, national_id=nid,
                                      first_name=cit.first_name + '_CHANGED')
        existing2 = CitizenFactory(pk=3)
        TempCitizenFactory(pk=existing2.pk, **model_to_dict(existing2))
        stats = mirror_database(
            from_model=TempCitizen,
            to_model=Citizen
        )
        self.assertEqual(2, stats.unchanged_count)
        self.assertEqual(1, stats.modified_record_count)
        self.assertEqual(0, stats.new_record_count)
        self.assertEqual(0, stats.not_there_anymore_count)
        c = Citizen.objects.get(pk=cit.pk)
        self.assertEqual(temp_cit.first_name, c.first_name)

    def test_unchanged_record(self):
        cit = CitizenFactory()
        TempCitizenFactory(**model_to_dict(cit))

        stats = mirror_database(
            from_model=TempCitizen,
            to_model=Citizen
        )
        self.assertEqual(1, stats.unchanged_count)
        self.assertEqual(0, stats.modified_record_count)
        self.assertEqual(0, stats.new_record_count)
        self.assertEqual(0, stats.not_there_anymore_count)

    def test_record_gone_do_not_delete(self):
        cit = CitizenFactory()
        stats = mirror_database(
            from_model=TempCitizen,
            to_model=Citizen
        )
        self.assertEqual(0, stats.unchanged_count)
        self.assertEqual(0, stats.modified_record_count)
        self.assertEqual(0, stats.new_record_count)
        self.assertEqual(1, stats.not_there_anymore_count)
        # NOT deleted
        self.assertTrue(Citizen.objects.filter(pk=cit.pk).exists())

    def test_record_gone_do_not_delete_with_existing(self):
        existing = CitizenFactory(pk=1)
        TempCitizenFactory(pk=1, **model_to_dict(existing))
        cit = CitizenFactory(pk=2)
        existing2 = CitizenFactory(pk=3)
        TempCitizenFactory(pk=3, **model_to_dict(existing2))
        stats = mirror_database(
            from_model=TempCitizen,
            to_model=Citizen
        )
        self.assertEqual(2, stats.unchanged_count)
        self.assertEqual(0, stats.modified_record_count)
        self.assertEqual(0, stats.new_record_count)
        self.assertEqual(1, stats.not_there_anymore_count)
        # NOT deleted
        self.assertTrue(Citizen.objects.filter(pk=cit.pk).exists())

    def test_missing_record_returned_in_from_model(self):
        """
        Citizen models have the concept of a 'missing' record, which is a record
        that was present in the Citizen model, but then absent from a
        subsequent CRA dump. We keep the record in the database,
        but mark it 'missing'. Our default manager for the Citizen model then
        filters out missing records, by default. This can create a problem if
        the record shows up again in a subsequent dump, because, if we use the
        default manager, then:
        * the record will not be present in the default `to_model` queryset
        * it will be present in the `from_model` queryset, and
        * when we try to add the record, there will be an IntegrityError.

        This tests to make sure we handle that case by using the special
        'unfiltered' queryset.
        """
        existing_but_missing = CitizenFactory(pk=1, missing=now())
        temp_citizen = TempCitizenFactory.build(pk=1, **model_to_dict(existing_but_missing))
        temp_citizen.missing = None
        temp_citizen.save()
        stats = mirror_database(
            from_model=TempCitizen,
            to_model=Citizen
        )
        self.assertEqual(0, stats.unchanged_count)
        self.assertEqual(1, stats.modified_record_count)
        self.assertEqual(0, stats.new_record_count)
        self.assertEqual(0, stats.not_there_anymore_count)
        self.assertTrue(Citizen.objects.filter(pk=existing_but_missing.pk).exists())
