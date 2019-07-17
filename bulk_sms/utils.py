import csv
import os
import signal
import logging
import functools

from uuid import uuid4
from collections import namedtuple

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils.translation import ugettext_lazy as _

from libya_elections.phone_numbers import is_valid_phone_number

logger = logging.getLogger(__name__)

FIELDS = ['number', 'message']
Line = namedtuple("Line", FIELDS)

PARSING_ERROR = _("Error found in line {line_number}: The row should only have the following "
                  "columns: {columns}.")
INVALID_PHONE_ERROR = _("Unable to parse number {number} as a phone number on row {line_number}")
BLANK_MESSAGE_ERROR = _("Message is blank on row {line_number}")


def can_approve_broadcast(user, raise_exception=True):
    if user.has_perm('bulk_sms.approve_broadcast'):
        return True
    if raise_exception:
        raise PermissionDenied


def is_staff(user):
    return user.is_staff


def validate_uploaded_file(file_path):
    """
    Parse the file to see if it's a valid bulk sms message upload file.

    If not, raises ValidationError

    """
    with open(file_path, encoding='utf-8') as f:
        reader = csv.reader(f)

        line_number = 0
        for row in reader:
            line_number += 1
            if any(row):
                try:
                    line = Line._make(row)
                except TypeError:
                    raise ValidationError(PARSING_ERROR.format(line_number=line_number,
                                                               columns=", ".join(FIELDS)))
                if not is_valid_phone_number(line.number):
                    raise ValidationError(INVALID_PHONE_ERROR.format(number=line.number,
                                                                     line_number=line_number))
                if not line.message.strip():
                    raise ValidationError(BLANK_MESSAGE_ERROR.format(line_number=line_number))


def save_uploaded_file(uploaded_file):
    """
    Save uploaded file to a temp file.
    Return file path to temp file.
    Be sure to clean up the temp file eventually...
    :param uploaded_file:
    :return:
    """
    temp_dir = settings.FILE_UPLOAD_TEMP_DIR or os.environ.get('TMPDIR', '/tmp')
    tmp_file_path = os.path.join(temp_dir, str(uuid4()) + ".csv")
    with open(tmp_file_path, 'wb+') as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)
    return tmp_file_path


def concurrency_safe_by_args(timeout=60, default=None):
    """
    Decorator that ensures no two instances of the wrapped method run concurrently
    with the same arguments.

    It works by adding a key to the cache based on the module and method signature
    (including values of arguments) for the wrapped function. If such a key
    already exists when the method is called, return the ``default`` value instead
    without calling the decorated function. The ``timeout`` determines the how long
    the key should persist in case we're not able to delete it manually.
    """
    def actual_decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # based on http://docs.celeryproject.org/en/latest/tutorials/task-cookbook.html
            args_sig = ','.join([str(a) for a in args])
            kwargs_sig = ','.join([':'.join([k, str(v)]) for k, v in kwargs.items()])
            lock_id = '.'.join(['lock', func.__module__, func.__name__,
                                args_sig, kwargs_sig])
            logger.debug(lock_id)
            # cache.add fails if the key already exists
            if not cache.add(lock_id, 'true', timeout):
                logger.warning('Not calling {0} because it appears someone else '
                               'is already calling it with these args ({1}) and '
                               'kwargs ({2}).'.format(func.__name__, args_sig, kwargs_sig))
                return default
            try:
                return func(*args, **kwargs)
            finally:
                # memcache delete is very slow, but we have to use it to take
                # advantage of using add() for atomic locking
                cache.delete(lock_id)
        return wrapper
    return actual_decorator


class SignalManager(object):
    """
    Functions as a signal handler stack that saves previous signal handlers and
    allows new ones to be pushed and popped. Only the current handler is called
    when a signal is actually raised. Intended to be used as a singleton.
    """
    def __init__(self):
        self._saved_handlers = {}

    def push(self, signum, handler):
        """
        Install a signal handler, saving the previous one (if any) first.
        """
        logger.debug('Installing signal handler {0}.'.format(signum))
        if signum not in self._saved_handlers:
            self._saved_handlers[signum] = []
        self._saved_handlers[signum].append(signal.getsignal(signum))
        signal.signal(signum, handler)

    def pop(self, signum):
        """
        Restore the saved signal handler that we replaced in
        ``push_signal_handler``, if any.
        """
        if signum not in self._saved_handlers or len(self._saved_handlers[signum]) == 0:
            raise ValueError('No signal handlers have been saved for signal {0}.'.format(signum))
        logger.debug('Restoring signal handler for signal {0}.'.format(signum))
        current = signal.getsignal(signum)
        signal.signal(signum, self._saved_handlers[signum].pop())
        return current


# singleton for managing signals
signal_manager = SignalManager()
