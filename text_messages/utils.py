from django.core.cache import cache
from django.utils.translation import get_language

# We store this in the cache to indicate that there's no such
# message in the database.
DOES_NOT_EXIST = "ZZZ"


def _get_cache_version():
    """Return the current version number that we're using to cache
    message texts. This is incremented anytime we need to invalidate
    currently cached values.
    """
    from .models import MessageText  # avoid circular import
    cache_version = cache.get(MessageText.CACHE_VERSION_KEY, default=1)
    return cache_version


def get_message(number):
    """
    Return the MessageText object with the given number,
    or raise ValueError.

    Uses a cache so it's not continually hitting the database to look up
    the same messages.
    """
    from .models import MessageText  # avoid circular import

    cache_version = _get_cache_version()

    message_key = "%s_%d" % (MessageText.CACHE_KEY, number)
    message = cache.get(message_key, version=cache_version)
    if message is None:
        try:
            message = MessageText.objects.get(number=number)
        except MessageText.DoesNotExist:
            message = DOES_NOT_EXIST
        cache.set(message_key, message, version=cache_version)
    if message == DOES_NOT_EXIST:
        raise ValueError("No such message code: %s" % number)
    return message


def clear_cache(*args, **kwargs):
    """
    Invalidate currently cached messages by starting to use a higher
    cache version number for our caching.

    Arguments are ignored so we can call this from a signal handler.
    """
    from .models import MessageText  # avoid circular import
    cache_version = _get_cache_version()
    cache_version += 1
    cache.set(MessageText.CACHE_VERSION_KEY, cache_version)


def pick_text(text_en, text_ar):
    """
    Return text_en if current language is english or text_ar is not set,
    else text_ar
    """
    return text_en if (get_language() == 'en' or not text_ar) else text_ar


def maybe_add_message_to_database(
        Model,
        number,
        label,
        msg_en,
        msg_ar,
        enhanced_en='',
        enhanced_ar='',
):
    """If there's not already a message in MessageText with this number,
    add one with this content. If there is, do nothing.
    """
    Model.objects.get_or_create(
        number=number,
        defaults=dict(
            label=label,
            msg_en=msg_en,
            msg_ar=msg_ar,
            enhanced_en=enhanced_en,
            enhanced_ar=enhanced_ar,
        )
    )
