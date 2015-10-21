from django.contrib.auth import get_user_model

import factory


DEFAULT_USER_PASSWORD = 'password'


class UserFactory(factory.DjangoModelFactory):
    FACTORY_FOR = get_user_model()

    username = factory.Sequence(lambda n: 'user%s' % n)
    password = DEFAULT_USER_PASSWORD
    email = factory.LazyAttribute(lambda obj: '%s@example.com' % obj.username)

    # From factory boy docs
    # (http://factoryboy.readthedocs.org/en/latest/recipes.html#custom-manager-methods)
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override the default ``_create`` with our custom call."""
        # We use this so our password gets encrypted and the user is otherwise
        # set up the same as a real user.
        manager = cls._get_manager(model_class)
        # The default would use ``manager.create(*args, **kwargs)``
        if kwargs.pop('is_superuser', False):
            return manager.create_superuser(*args, **kwargs)
        return manager.create_user(*args, **kwargs)
