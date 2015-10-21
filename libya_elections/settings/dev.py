import sys

from libya_elections.settings.base import *  # noqa

DEBUG = True
TEMPLATE_DEBUG = DEBUG

MIDDLEWARE_CLASSES += (
    'debug_toolbar.middleware.DebugToolbarMiddleware',
)

SECRET_KEY = 'dummy secret key for testing only'

INTERNAL_IPS = ('127.0.0.1', )

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'
NOSE_ARGS = ['--nologcapture']

CELERY_ALWAYS_EAGER = False

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
        "sendsms_url": os.getenv("vumi_http_sendsms_url", "http://127.0.0.1:9000/send/"),
    },
}

INSTALLED_APPS = list(INSTALLED_APPS)

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
    CELERY_ALWAYS_EAGER = True
    CELERY_EAGER_PROPAGATES_EXCEPTIONS = True

    PASSWORD_HASHERS = (
        'django.contrib.auth.hashers.SHA1PasswordHasher',
        'django.contrib.auth.hashers.MD5PasswordHasher',
    )

    CAPTCHA_TEST_MODE = True

    REPORTING_REDIS_KEY_PREFIX = 'os_rapi_ut_'

    # use default storage for tests, since we don't run collectstatic for tests
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
else:
    # Enable all tools for local development, but not when running tests.
    ENABLE_ALL_TOOLS = True
    # Enable django-debug-toolbar if not running tests
    INSTALLED_APPS[-1:-1] = (
        "debug_toolbar",
    )

VOTER_API_USER = 'test_voter_user'
VOTER_API_PASSWORD = 'test_voter_pass'
