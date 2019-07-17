from django.apps import apps
from django.contrib import admin
from django.test import TestCase
from django.utils import timezone

from bulk_sms.models import Batch, BulkMessage
from bulk_sms.tests.factories import BatchFactory
from bulk_sms.tests.factories import BulkMessageFactory
from register.models import Person, SMS
from register.tests.factories import PersonFactory, SMSFactory
from voting.models import Election
from voting.tests.factories import ElectionFactory

from ..abstract import AbstractTrashBinModel, AbstractBaseModel
from ..admin_models import LibyaAdminModel


THIRD_PARTY_MODULES = [
    'captcha',
    'django',
    'rapidsms',
    'registration',
    'civil_registry',  # sort of... it's a mirror of an external data source
    'bread',  # trying to keep this as a stand-alone-able app
]


class BaseModelTest(TestCase):
    """Ensure that all of our models inherit from our custom base model"""
    def test_all_our_apps_should_use_base_model(self):
        for model in apps.get_models():
            # skip third party modules
            if model.__module__.split('.')[0] in THIRD_PARTY_MODULES:
                continue
            self.assertTrue(issubclass(model, AbstractBaseModel),
                            "%s needs to be a subclass of AbstractBaseModel" % model)


class TrashBinManagerTest(TestCase):
    def test_dont_get_deleted_objects_by_default(self):
        person = PersonFactory()
        self.assertIn(person, Person.objects.all())
        person.deleted = True
        person.save()
        self.assertNotIn(person, Person.objects.all())

    def test_can_specifically_get_deleted_objects(self):
        person = PersonFactory(deleted=True)
        self.assertIn(person, Person.objects.deleted())

    def test_unfiltered_manager_gets_deleted_objects(self):
        person = PersonFactory(deleted=True)
        self.assertIn(person, Person.objects.unfiltered())

    # make sure to test any models with their own managers

    def test_dont_get_deleted_sms_by_default(self):
        sms = SMSFactory(deleted=True)
        self.assertNotIn(sms, SMS.objects.all())

    def test_dont_get_deleted_election_by_default(self):
        election = ElectionFactory(deleted=True)
        self.assertNotIn(election, Election.objects.all())

    def test_dont_get_deleted_batch_by_default(self):
        batch = BatchFactory(deleted=True)
        self.assertNotIn(batch, Batch.objects.all())

    def test_dont_get_deleted_bulkmessage_by_default(self):
        bulkmessage = BulkMessageFactory(deleted=True)
        self.assertNotIn(bulkmessage, BulkMessage.objects.all())

    # test that we can update deleted objects

    def test_update_deleted_object(self):
        person = PersonFactory(deleted=True)
        # undelete the object
        person.deleted = False
        person.save()
        undeleted_person = Person.objects.get(id=person.id)
        self.assertFalse(undeleted_person.deleted)


class AbstractTimestampModelTest(TestCase):
    def setUp(self):
        self.before = timezone.now()
        self.obj = PersonFactory()

    def test_creation_date(self):
        after = timezone.now()
        self.assertGreater(self.obj.creation_date, self.before)
        self.assertLess(self.obj.creation_date, after)

    def test_modification_date(self):
        modification_date = self.obj.modification_date
        self.assertTrue(modification_date)
        self.obj.save()
        self.assertGreater(self.obj.modification_date, modification_date)


class LibyaAdminModelTest(TestCase):

    def test_all_our_models_use_our_admin(self):
        admin.autodiscover()
        for model, modeladmin in admin.site._registry.items():
            # skip third party modules
            if model.__module__.split('.')[0] in THIRD_PARTY_MODULES:
                continue
            if issubclass(model, AbstractTrashBinModel):
                self.assertTrue(issubclass(type(modeladmin), LibyaAdminModel),
                                "%s needs to use LibyaAdminModel" % model)
