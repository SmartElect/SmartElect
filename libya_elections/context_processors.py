from __future__ import unicode_literals
from __future__ import division
import datetime


def current_timestamp(request):
    """Return now in [dd month_name year timestamp] format"""
    return {
        'current_timestamp': datetime.datetime.now().strftime('%d %B %Y %H:%M:%S')
    }
