from django.db.models import get_models
from django.test import TestCase


class FieldVerboseNameTest(TestCase):
    """Ensure that all of our model fields have the verbose_name attr populated."""
    # We ignore 3rd party modules
    IGNORE_THESE_MODULES = [
        'captcha',
        'django',
        'djcelery',
        'rapidsms',
        'registration',
    ]

    # We ignore any models that don't need translated verbose names (because they don't appear in
    # the BREAD views).
    IGNORE_THESE_MODELS = [
        'bulk_sms.Batch',
        'help_desk.ScreenRecord',
        'civil_registry.CitizenMetadata',
        'civil_registry.DumpFile',
        'bread.BreadTestModel',
    ]

    MESSAGE = "{}.{}.verbose_name is not a translated string that starts with a lower case letter."

    def test_verbose_name_on_fields(self):
        """Ensure that all of our model fields have the verbose_name attr populated."""
        for model in get_models():
            if model.__module__.split('.')[0] not in self.IGNORE_THESE_MODULES:
                model_name = model._meta.app_label + '.' + model._meta.object_name
                if model_name not in self.IGNORE_THESE_MODELS:
                    for field in model._meta.fields:
                        message = self.MESSAGE.format(model, field)
                        # verbose_name must not be '' or None
                        self.assertTrue(bool(field.verbose_name), message)
                        lower_verbose_name = field.verbose_name.lower()
                        if lower_verbose_name != 'id':
                            # verbose_name is either a translated string, in which case the class
                            # will be django.utils.functional.__proxy__, or str/unicode if the
                            # author forgot to translate it. The latter is easier to test for and
                            # won't break if Django eventually changes its class hierarchy.
                            self.assertFalse(isinstance(field.verbose_name, basestring), message)
                            # We don't want Init Caps for verbose names.
                            self.assertEqual(lower_verbose_name[0], field.verbose_name[0], message)
                        # else:
                            # In most (all?) cases, Django creates the id field so we don't control
                            # the verbose name.


class ModelVerboseNamesTest(TestCase):
    """Ensure that all of our models have verbose_name and verbose_name_plural populated."""
    # We ignore 3rd party modules
    IGNORE_THESE_MODULES = [
        'captcha',
        'django',
        'djcelery',
        'rapidsms',
        'registration',
    ]

    # We ignore any models that don't need translated verbose names (because they don't appear in
    # the BREAD views).
    IGNORE_THESE_MODELS = [
        'bulk_sms.Batch',
        'help_desk.ScreenRecord',
        'civil_registry.TempCitizen',
        'civil_registry.CitizenMetadata',
        'civil_registry.DumpFile',
        'bread.BreadTestModel',
    ]

    MESSAGE = \
        "{}.verbose_name{} is not a translated string that starts with a lower case letter."

    def test_verbose_names_on_models(self):
        """Ensure that all of our models have verbose_name and verbose_name_plural populated."""
        for model in get_models():
            if model.__module__.split('.')[0] not in self.IGNORE_THESE_MODULES:
                model_name = model._meta.app_label + '.' + model._meta.object_name
                if model_name not in self.IGNORE_THESE_MODELS:
                    # Test both verbose_name and verbose_name_plural
                    for name, descriptor in ((model._meta.verbose_name, ''),
                                             (model._meta.verbose_name_plural, '_plural')):
                        message = self.MESSAGE.format(model, descriptor)

                        # verbose name must not be '' or None
                        self.assertTrue(bool(name), message)

                        # verbose name is either a translated string, in which case the class
                        # will be django.utils.functional.__proxy__, or str/unicode if the
                        # author forgot to translate it. The latter is easier to test for and
                        # won't break if Django eventually changes its class hierarchy.
                        self.assertFalse(isinstance(name, basestring), message)
                        # We don't want Init Caps for verbose names.
                        self.assertEqual(name[0].lower(), name[0], message)
