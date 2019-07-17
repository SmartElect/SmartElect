from celery import Celery

# DON'T set a default Django settings module for the 'celery' program, to force
# it to be passed in through the environment.
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'libya_elections.settings.?')

app = Celery('libya_elections')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
