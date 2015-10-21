from django.db import models
from django.utils.translation import ugettext_lazy as _

from libya_elections.abstract import AbstractBaseModel


class ElectionReport(AbstractBaseModel):
    election = models.ForeignKey('voting.Election', unique=True, verbose_name=_('election'))
    report = models.TextField(_('report'))
    hq_reports = models.TextField(_('headquarters reports'))
    message_log = models.TextField(_('message log'))

    class Meta:
        verbose_name = _("election report")
        verbose_name_plural = _("election reports")
