import sys

from libya_elections.settings.base import *  # noqa

DEBUG = True

SECRET_KEY = 'dummy secret key for testing only'

INTERNAL_IPS = ('127.0.0.1', )

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

CELERY_TASK_ALWAYS_EAGER = False

INSTALLED_BACKENDS = {
    HTTPTESTER_BACKEND: {
        "ENGINE": "rapidsms.backends.database.DatabaseBackend",
    },
    "vumi-fake-smsc": {
        "ENGINE": "rapidsms.backends.vumi.VumiBackend",
        # Default to localhost, but allow override
        "sendsms_url": os.getenv("vumi_fake_smsc_sendsms_url", "http://127.0.0.1:9000/send/"),
    },
    "vumi-http": {
        "ENGINE": "rapidsms.backends.vumi.VumiBackend",
        # Default to localhost, but allow override
        "sendsms_url": os.getenv("VUMI_HTTP_SENDSMS_URL", "http://127.0.0.1:9000/send/"),
    },
}

CACHES = {
    'default': {
        # Use same backend as in production
        'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
        # Assume memcached is local
        'LOCATION': '127.0.0.1:11211',
        'TIMEOUT': 60 * 60,  # one hour
    }
}

# Special test settings
if 'test' in sys.argv:
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

    PASSWORD_HASHERS = (
        'django.contrib.auth.hashers.SHA1PasswordHasher',
        'django.contrib.auth.hashers.MD5PasswordHasher',
    )

    CAPTCHA_TEST_MODE = True

    REPORTING_REDIS_KEY_PREFIX = 'os_reporting_api_ut_'

    # use default storage for tests, since we don't run collectstatic for tests
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
else:
    # Enable all tools for local development, but not when running tests.
    ENABLE_ALL_TOOLS = True
    # Enable django-debug-toolbar if not running tests
    INSTALLED_APPS[-1:-1] = (
        "debug_toolbar",
    )
    DEBUG_TOOLBAR_PATCH_SETTINGS = False
    MIDDLEWARE += (
        'debug_toolbar.middleware.DebugToolbarMiddleware',
    )
