SmartElect
==========

Below you will find basic setup and deployment instructions for the SmartElect
project. To begin you should have the following applications installed on your
local development system:

- Python = 2.7
- `pip >= 1.5.4 <http://www.pip-installer.org/>`_
- `virtualenv >= 1.11 <http://www.virtualenv.org/>`_
- `virtualenvwrapper >= 3.0 <http://pypi.python.org/pypi/virtualenvwrapper>`_
- Postgres >= 9.1
- git >= 1.7
- memcached >= 1.4
- redis >= 2.10
- freetype
- Mac Command line dev tools


Getting Started
---------------

To setup your local environment you should create a virtualenv and install the
necessary requirements::

    mkvirtualenv -p `which python2.7` smartelect
    $VIRTUAL_ENV/bin/pip install -U -r $PWD/requirements/dev.txt

Then create a local settings file and set your ``DJANGO_SETTINGS_MODULE`` to use it::

    cp libya_elections/settings/local.example.py libya_elections/settings/local.py
    echo "export DJANGO_SETTINGS_MODULE=libya_elections.settings.local" >> $VIRTUAL_ENV/bin/postactivate
    echo "unset DJANGO_SETTINGS_MODULE" >> $VIRTUAL_ENV/bin/postdeactivate

Exit the virtualenv and reactivate it to activate the settings just changed::

    deactivate
    workon smartelect

Create the Postgres database and run the initial migrate::

    createdb -E UTF-8 smartelect
    python manage.py migrate

Create a superuser::

    python manage.py createsuperuser

Redis is required.  Install the server with ``brew install redis`` (OS X) or ``sudo apt-get install redis-server``
(some Linux), or something else.  If Redis is listening on a non-standard port or not accessible over ``localhost``,
use the ``REPORTING_REDIS_SETTINGS`` in ``base.py`` to configure it.

You should now be able to run the development server::

    python manage.py runserver

To run the test suite (including flake8 and a coverage report)::

    ./run_tests.sh

We use the `django-nose <https://github.com/django-nose/django-nose>`_ test runner which offers some
extra features. You can set the env var ``REUSE_DB=1`` to have Django reuse the test database
between test runs, saving many seconds in test startup time. If you do, be aware that test runs will
not automatically pick up new migrations anymore, so if you create a new migration, you'll have to
unset ``REUSE_DB`` for one test run to pick up the new migrations::

    REUSE_DB=1 ./run_tests.sh

You can also tell django-nose to stop at the first test failure, and to only rerun failed tests.
This is very handy when you're focused on a new feature and don't want to run the whole test suite
with each change, but do want to run the whole test suite once you have your test working (to make
sure that your working code didn't break something else). Put this in ``$HOME/.noserc``::

    [nosetests]
    # failed=1 means only run tests that failed on a previous run.
    # Note though that failed tests are only recorded when failed=1
    # is set, which means it's not very useful unless you keep it
    # set.
    failed=1

    # stop=1 means stop on the first failure. This sometimes breaks tests by leaving
    # the database in an unclean state. If you hit weird test failures after the
    # first one, try adding FORCE_DB=1 (just one time); it's the anti-REUSE_DB=1
    # and will ensure running the tests with a fresh new test database.
    stop=1

Next, we'll discuss setting up celery and celerybeat. This may not be necessary for all purposes, so
see below for a simpler alternative mechanism. If that simpler mechanism is not sufficient, then you
will need to setup celery. In a separate shell, run the celery workers::

    python manage.py celery worker

- If this fails due to an error connecting to RabbitMQ, ensure that RabbitMQ is installed and running.  (Ubuntu: ``sudo apt-get install rabbitmq-server``)

In a separate shell, run the ``celerybeat`` process::

    python manage.py celerybeat

*The* ``celerybeat`` *and celery worker processes will need to be manually recycled to pick up code changes.*

An alternative mechanism for running Celery tasks in a development environment without RabbitMQ is
to run tasks synchronously in a separate process.  In order to accomplish this, set
``CELERY_ALWAYS_EAGER = True`` and ``CELERY_EAGER_ALWAYS_PROPAGATES_EXCEPTIONS = True`` in local.py.
You'll still need the celerybeat process if you want to test recurring tasks, but if you only want
to generate data for the dashboard, then run these commands::

    python manage.py create_reporting_api_test_data --yes-delete-my-data --num-registration-dates=30
    python manage.py generate_reporting_api_reports

Reporting API and VR Dashboard
------------------------------

The integrated VR Dashboard accesses the reports directly, not over HTTP.  If you need to enable access to reporting
API reports over HTTP, such as for testing or for access from the legacy vr-dashboard application:

- Configure the Basic auth user and password by setting ``REPORTING_API_USERNAME`` and ``REPORTING_API_PASSWORD``
  in the environment or in ``local.py``.

The reports are generated by Celery tasks, with the normal schedule defined by ``REPORT_GENERATION_INTERVALS`` in
``base.py``.  When testing, smaller intervals will likely be needed in ``local.py``, such as in the following example::

    from datetime import timedelta
    REPORT_GENERATION_INTERVALS = {
        'default': timedelta(minutes=1),  # used for reports that don't have an overridden schedule below
        # 'election_day': timedelta(minutes=5),
        # 'registrations': timedelta(minutes=7)
    }

(And remember to start the Celery process(es), which you might not normally need.)

Source
------

Developed for the Libya High National Elections Commission by `Caktus Consulting Group
<https://www.caktusgroup.com/>`_.
