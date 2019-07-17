import datetime

from django.conf import settings


def current_timestamp(request):
    """Return now in [dd month_name year timestamp] format"""
    return {
        'current_timestamp': datetime.datetime.now().strftime('%d %B %Y %H:%M:%S')
    }


def environment(request):
    """Return settings.ENVIRONMENT"""
    return {
        'ENVIRONMENT': settings.ENVIRONMENT,
    }
