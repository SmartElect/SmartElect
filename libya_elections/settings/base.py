# Django settings for libya_elections project.
import datetime
import os

from django.utils.translation import ugettext_lazy as _

# PROJECT_PATH is the libya_elections dir that contains the settings dir
PROJECT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

# PROJECT ROOT is the top dir of the source tree
PROJECT_ROOT = os.path.abspath(os.path.join(PROJECT_PATH, os.pardir))


DEBUG = True

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'DISABLE_SERVER_SIDE_CURSORS': True,
        'NAME': os.getenv('DB_NAME', 'open_source_elections'),
        'USER': os.getenv('DB_USER', ''),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', ''),
        'PORT': os.getenv('DB_PORT', ''),
    }
}

SLAVE_DATABASES = []

if int(os.getenv('DB_HAVE_LOCAL_READ_REPLICA', 0)) == 1:
    replica = DATABASES['default'].copy()
    replica['NAME'] += '_read_replica'
    DATABASES['read_replica'] = replica
    SLAVE_DATABASES = ['read_replica']
    DATABASE_ROUTERS = ['multidb.PinningMasterSlaveRouter']

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'Libya'

# Accepted language codes are limited to 'en' and 'ar'. Django will normalize
# other language codes to one of these two.
# See https://github.com/hnec-vr/libya-elections/issues/1351
LANGUAGES = (
    ('ar', _('Arabic')),
    ('en', _('English')),
)
LANGUAGE_CODE = 'en'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# Override selected locale settings.
FORMAT_MODULE_PATH = 'libya_site.formats'

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = os.path.join(PROJECT_ROOT, 'public', 'media')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = '/media/'

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = os.path.join(PROJECT_ROOT, 'public', 'static')

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# Additional locations of static files
STATICFILES_DIRS = (
    os.path.join(PROJECT_PATH, 'static'),
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    #    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# https://docs.djangoproject.com/en/1.8/ref/contrib/staticfiles/#manifeststaticfilesstorage
# Store static files with a name which includes their MD5 hash, to eliminate stale CSS
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(PROJECT_PATH, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.debug',
                'django.template.context_processors.media',
                'django.template.context_processors.request',
                'django.template.context_processors.i18n',
                'django.template.context_processors.static',
                'voting.context_processors.current_election',
                'libya_elections.context_processors.current_timestamp',
                'libya_elections.context_processors.environment',
            ],
        },
    },
]

MIDDLEWARE = (
    'multidb.middleware.PinningRouterMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'libya_elections.middleware.GroupExpirationMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'libya_elections.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'libya_elections.wsgi.application'

FIXTURE_DIRS = (
    os.path.join(PROJECT_PATH, 'fixtures'),
)

INSTALLED_APPS = [
    # libya_site first, so its templates override django's templates
    'libya_site',

    # Django apps
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'django.contrib.humanize',

    # External apps
    'captcha',
    "django_tables2",
    'fixture_magic',
    'registration',
    'selectable',
    'bread',

    # Our apps
    # apps, to process incoming msgs, must be before contrib.handlers or
    # other RapidSMS
    'voting',  # Should be early because on voting day, it overrides other possible messages

    'audit',
    'bulk_sms',
    'changesets',
    'civil_registry',
    'help_desk',
    'polling_reports',
    'register',
    'reporting_api',
    'rollgen',
    'staff',
    'text_messages',
    'subscriptions',
    'vr_dashboard',

    # RapidSMS
    "rapidsms",
    "rapidsms.backends.database",
    "rapidsms.router.celery",
    "httptester",  # Forked from contrib to add to_addr
    "rapidsms.contrib.handlers",
]

# This is for local development.  It is completely overridden in
# testing and production. It logs only to local files, and
# at a more detailed level than we'd want in production.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'root': {
        'level': 'DEBUG',  # Include all the way to DEBUG, if a logger sends it
        'handlers': ['file'],
    },
    'formatters': {
        'basic': {
            'format': '%(asctime)s %(name)-20s %(levelname)-8s %(message)s',
        },
    },
    'handlers': {
        # Not used by default, but handy for local debugging when needed.
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'basic',
        },
        'file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'basic',
            'filename': os.path.join(PROJECT_ROOT, 'libya_elections.log'),
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 10,
        },
    },
    'loggers': {
        # These 2 loggers must be specified, otherwise they get disabled
        # because they are specified by django's DEFAULT_LOGGING and then
        # disabled by our 'disable_existing_loggers' setting above.
        # BEGIN required loggers #
        'django': {
            'handlers': [],
            'propagate': True,
        },
        'py.warnings': {
            'handlers': [],
            'propagate': True,
        },
        # END required loggers #
        'rapidsms': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'register': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    }
}

# django-simple-captcha settings
CAPTCHA_LENGTH = 4
CAPTCHA_FONT_SIZE = 42
CAPTCHA_NOISE_FUNCTIONS = ('captcha.helpers.noise_dots',)
CAPTCHA_LETTER_ROTATION = (-10, 10)
CAPTCHA_CHALLENGE_FUNCT = 'libya_site.utils.random_digit_challenge'

# Application settings
ACCOUNT_ACTIVATION_DAYS = 3
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
SESSION_COOKIE_AGE = 6 * (60 * 60)  # logout after 6 hours of inactivity

# order matters
POLLING_REPORT_HANDLERS = (
    'polling_reports.handlers.ReportsShortCodeHandler',
)

REGISTER_HANDLERS = (
    'register.handlers.VoterQueryCitizenLookupHandler',  # This handler must be first
    'register.handlers.VoterQueryWrongLengthNIDHandler',
    'register.handlers.RegistrationMessageHandler',
    'register.handlers.WrongNIDLengthHandler',
    'register.handlers.WrongCenterIDLengthHandler',
    'register.handlers.DefaultHandler',  # This handler must be last!
)

RAPIDSMS_HANDLERS = POLLING_REPORT_HANDLERS + REGISTER_HANDLERS

RAPIDSMS_ROUTER = "rapidsms.router.celery.CeleryRouter"

# RapidSMS sends DEFAULT_RESPONSE only if no other apps handle the msg.
# Should only occur if msg is to a shortcode that we don't expect.
# Setting it to `None` tells RapidSMS not to send any response.
DEFAULT_RESPONSE = None

# Default to False because we expect MNO to do the spliting
SPLIT_LONG_MESSAGES = False
MAX_OUTGOING_LENGTH = 70
MSG_ORDER_NUMBER_LENGTH = 8  # len(' [23/88]')
OUTGOING_MSG_TRANSFORMATIONS = {
    '8)': '8 )',
    '(8': '( 8',
}

# SMS language settings
OUTGOING_MESSAGE_LANGUAGE = "ar"
LOCALE_PATHS = (os.path.join(PROJECT_ROOT, 'locale'), )

# Incoming numbers might be prefixed by this, not sure.  We'll allow it if so.
LIBYA_COUNTRY_CODE = "218"
# Incoming numbers we'll respond to
# These are for testing. Update to correct values in deploy.py
REGISTRATION_SHORT_CODE = '10020'
VOTER_QUERY_SHORT_CODE = REGISTRATION_SHORT_CODE
REPORTS_SHORT_CODE = '10040'
SHORT_CODES = {REGISTRATION_SHORT_CODE, REPORTS_SHORT_CODE}

# Regular expression (string) to match valid phone numbers that can be used
# in white lists, black lists, staff numbers, bulk SMS target lists, etc etc.
# The formats of phone numbers currently valid in Libya:
#   2189 + 8 digits  (Libyana, Al Madar)
#   88216 + 8 digits  (Thuraya)
# If this changes, also change libya_elections.constants.PHONE_NUMBER_MSG.
PHONE_NUMBER_REGEX = r'^2189\d{8}$|^88216\d{8}$'
MAX_PHONE_NUMBER_LENGTH = 13

# This is the maximum number of registrations allowed on a phone
MAX_REGISTRATIONS_PER_PHONE = 2

# Do we want to load test?
# Setting this to true allows anyone access to a URL which will delete items
# from the database and create test data for the load test. It should
# be false on any production site.
LOAD_TEST = False

CELERY_TASK_ACKS_LATE = True
# Automatic Celery routing
CELERY_TASK_ROUTES = {
    'rapidsms.router.celery.tasks.send_async': {'queue': 'send_async'},
    'bulk_sms.tasks.upload_bulk_sms_file': {'queue': 'upload_bulksms'},
    'audit.tasks.audit_sms': {'queue': 'audit'},
    'audit.tasks.parse_logs': {'queue': 'audit'},
    'rollgen.tasks.run_roll_generator_job': {'queue': 'rollgen'},
}

# Enable tools based on dates
ENABLE_ALL_TOOLS = False  # Override dates for everything

# Polling reporting
# If a report of turnout exceeds SUSPICIOUS_TURNOUT_THRESHOLD, the system will suggest to the
# reporter to double check the value. It's a percentage expressed as a value from 0.00 to 1.00.
# See ticket #1004.
SUSPICIOUS_TURNOUT_THRESHOLD = 0.90

# production? testing?
ENVIRONMENT = os.getenv('ENVIRONMENT', '(environment not set)')

# site domain
SITE_DOMAIN = "%s.example.com" % ENVIRONMENT
DEFAULT_FROM_EMAIL = "no-reply@%s" % SITE_DOMAIN
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Outgoing BulkSMS settings
BULKSMS_DEFAULT_MESSAGES_PER_SECOND = 50
BULKSMS_DEFAULT_CONCURRENT_WORKERS = 10
# Backends to use (if we can't find number associated with a backend already)
BULKSMS_BACKENDS = ('almadar', 'libyana')

# Name of the backend to be used for web testing
HTTPTESTER_BACKEND = 'message_tester'

# How long people are granted an exception to register from any phone
# after calling the help desk
LENGTH_OF_REGISTRATION_UNLOCKING = datetime.timedelta(hours=12)

VUMI_LOGS = []
# Default schedule - importers can add to this
CELERY_BEAT_SCHEDULE = {}

# Number of approvals needed in order to activate a change set
MINIMUM_CHANGESET_APPROVALS = 2

# N_MAX_COPY_CENTERS limits how many copy centers can reference the same original (non-copy) center.
N_MAX_COPY_CENTERS = 6

# Voting age
VOTING_AGE_IN_YEARS = 18

# Basic auth support for reporting-api access by vr-dashboard
# Must be set in environment to allow access
REPORTING_API_USERNAME = os.getenv('REPORTING_API_USERNAME', '')
REPORTING_API_PASSWORD = os.getenv('REPORTING_API_PASSWORD', '')

# Settings for use of Redis by reporting_api, in the form of arguments to
# the StrictRedis constructor.  See
# http://redis-py.readthedocs.org/en/latest/index.html#redis.StrictRedis
REPORTING_REDIS_SETTINGS = {
    'host': os.getenv('REDIS_MASTER', 'localhost'),
}
REPORTING_REDIS_REPLICA_SETTINGS = {
    # fall back to the master host, if no replica is provided in env.sls
    'host': os.getenv('REDIS_REPLICA', REPORTING_REDIS_SETTINGS['host']),
}

# Unique development prefix for Redis keys used by reporting api
# (must be overridden for staging, prod, and test, to avoid collisions when
# different instances share a Redis server)
REPORTING_REDIS_KEY_PREFIX = 'os_reporting_api_dev_'

# can be set to None to disable report generation
REPORT_GENERATION_INTERVALS = {
    # the "default" interval applies to any reports not listed separately
    'default': datetime.timedelta(minutes=30),
    # 'election_day': datetime.timedelta(minutes=10),
    'registrations': datetime.timedelta(minutes=10)
}

# Begin Roll generator constants
# Some of these numbers come from the document 'Polling Planning Rules eng 20140526 0900.docx'
# ROLLGEN_REGISTRATIONS_PER_PAGE_REGISTRATION controls the number of registrants per printed page
# for registration (in-person and exhibitions) phases. ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_BOOK
# and ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_LIST control the number of registrants per printed page
# for the book and list in the polling phase.
ROLLGEN_REGISTRATIONS_PER_PAGE_REGISTRATION = 25
ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_BOOK = 15
ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_LIST = 15
# ROLLGEN_REGISTRANTS_PER_STATION_MAX controls the max number of registrations that
# station_distributor() will put at a station. In rare cases it can be exceeded; see the code for
# gory details.
ROLLGEN_REGISTRANTS_PER_STATION_MAX = 550
# ROLLGEN_UNISEX_TRIGGER controls the number of registrants below which male and female stations
# may be combined to create a unisex station. The actual rules are complicated. See
# station_distributor() for complete details.
ROLLGEN_UNISEX_TRIGGER = 25
# Center names are truncated to ROLLGEN_CENTER_NAME_TRUNCATE_AFTER characters in some cases to
# fit on the space provided in the PDF.
ROLLGEN_CENTER_NAME_TRUNCATE_AFTER = 42
# ROLLGEN_OUTPUT_DIR determines where rollgen writes its files. The value here is an OK but
# slightly messy choice for developers. You probably want to define something more convenient in
# local.py. This is also defined in deploy.py
ROLLGEN_OUTPUT_DIR = './rollgen/'
# End Roll generator constants


BREAD = {
    'DEFAULT_BASE_TEMPLATE': 'libya_site/staff.html',
}

# Django cache prefix
KEY_PREFIX = 'ose'

# Should the public dashboard be hidden from the public?
HIDE_PUBLIC_DASHBOARD = True
PUBLIC_REDIRECT_URL = 'https://example.com'
