from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext_lazy as _

from libya_elections.abstract import AbstractTimestampTrashBinModel


class Subscription(AbstractTimestampTrashBinModel):
    DISCREPANCIES = 1
    TYPES = [
        (DISCREPANCIES, _('SMS Discrepancies'))
    ]
    user = models.ForeignKey(User, verbose_name=_('user'),
                             on_delete=models.CASCADE)
    subscription_type = models.IntegerField(_('subscription type'), choices=TYPES,
                                            default=DISCREPANCIES)

    def __str__(self):
        return self.user.email

    class Meta:
        permissions = [
            ('browse_subscription', "Browse subscriptions"),
            ('read_subscription', "Read subscriptions"),
        ]
        verbose_name = _("email alert subscription")
        verbose_name_plural = _("email alert subscriptions")
        unique_together = (('user', 'subscription_type'),)
