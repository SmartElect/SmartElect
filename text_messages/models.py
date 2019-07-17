from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.utils.translation import ugettext_lazy as _

from libya_elections.abstract import AbstractTimestampTrashBinModel
from text_messages.utils import clear_cache


class MessageText(AbstractTimestampTrashBinModel):
    """
    This model manages the text (English & Arabic) of text messages that
    we send.

    (It is not a generalized text translation utility.)
    """
    # We combine this with the message number and use the result as a cache key
    CACHE_KEY = 'message_text_cache'
    # We store the current cache version here in the cache
    CACHE_VERSION_KEY = 'message_text_version'

    number = models.IntegerField(_('number'), primary_key=True)
    label = models.CharField(
        verbose_name=_("label"),
        max_length=80,
    )
    msg_en = models.TextField(
        verbose_name=_("english"),
        max_length=512,
    )
    msg_ar = models.TextField(
        verbose_name=_("arabic"),
        max_length=512)
    enhanced_en = models.TextField(
        verbose_name=_("english repeat message"),
        max_length=512, blank=True, default='')
    enhanced_ar = models.TextField(
        verbose_name=_("arabic repeat message"),
        max_length=512, blank=True, default='')
    description = models.TextField(
        verbose_name=_("description"),
        blank=True, default='')
    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("last updated by"),
        null=True,
        on_delete=models.CASCADE)

    class Meta(object):
        verbose_name = _("message text")
        verbose_name_plural = _("message texts")
        ordering = ['number']

    @property
    def msg(self):
        """Return msg_en or msg_ar depending on current language"""
        from .utils import pick_text
        return pick_text(self.msg_en, self.msg_ar)

    @property
    def enhanced(self):
        """Return enhanced_en or enhanced_ar depending on current language"""
        from .utils import pick_text
        return pick_text(self.enhanced_en, self.enhanced_ar)

    def save(self, *args, **kwargs):
        # Clear cache, if any
        clear_cache()
        super(MessageText, self).save(*args, **kwargs)


post_delete.connect(clear_cache)
post_save.connect(clear_cache)
