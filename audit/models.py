from __future__ import unicode_literals

from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db import models
from django.utils.translation import ugettext_lazy as _

from libya_elections.abstract import AbstractTimestampTrashBinModel
from libya_elections.constants import INCOMING, OUTGOING
from libya_elections.libya_bread import SMSFormatterMixin, VumilogFormatterMixin
from libya_elections.phone_numbers import format_phone_number, formatted_phone_number_tag


class VumiLog(AbstractTimestampTrashBinModel):
    """
    Stores vumi logs for every message that has been acknowledged as received and
    every message that has been sent.
    """
    DIRECTION_CHOICES = (
        (INCOMING, _("Incoming")),
        (OUTGOING, _("Outgoing")),
    )
    uuid = models.CharField(_('uuid'), max_length=50, db_index=True, unique=True)
    logged_date = models.DateTimeField(_('logged date'), null=True, blank=True)
    direction = models.IntegerField(_('direction'), choices=DIRECTION_CHOICES)
    to_addr = models.CharField(_('to address'), blank=True, max_length=255)
    from_addr = models.CharField(_('from address'), blank=True, max_length=255)
    content = models.TextField(_('content'), blank=True)
    is_audited = models.BooleanField(_('is audited'), default=False, db_index=True)
    raw_text = models.TextField(_('raw text'), blank=True)

    # Aliases to make this more similar to the SMS model
    @property
    def from_number(self):
        return self.from_addr

    @property
    def to_number(self):
        return self.to_addr

    class Meta:
        permissions = [
            ('read_vumilog', "Read vumilog records"),
        ]
        verbose_name = _("vumi log")
        verbose_name_plural = _("vumi logs")

    def __unicode__(self):
        return _("From {from_addr} to {to_addr}: {content}").format(
            from_addr=self.from_addr,
            to_addr=self.to_addr,
            content=self.content
        )

    def get_absolute_url(self):
        return reverse('read_vumilog', args=[self.id])

    @property
    def from_number_formatted(self):
        return format_phone_number(self.from_number)

    @property
    def from_number_formatted_tag(self):
        return formatted_phone_number_tag(self.from_number)

    @property
    def to_number_formatted(self):
        return format_phone_number(self.to_number)

    @property
    def to_number_formatted_tag(self):
        return formatted_phone_number_tag(self.to_number)

    @property
    def direction_formatted(self):
        return self.DIRECTIONS_MAP[self.direction]


class SMSTrail(SMSFormatterMixin, VumilogFormatterMixin, AbstractTimestampTrashBinModel):
    """
    Matches messages logged by Vumi with their corresponding RapidSMS
    counterpart.

    These are created programmatically, and never via the admin.

    At least one of 'sms' or 'vumi' must be populated before saving,
    and before calling report().
    """
    sms = models.OneToOneField("register.SMS", null=True, blank=True, unique=True,
                               verbose_name=_('sms'))
    vumi = models.OneToOneField(VumiLog, null=True, blank=True, unique=True,
                                verbose_name=_('vumi log'))

    class Meta:
        verbose_name = _("sms trail")
        verbose_name_plural = _("sms trails")

    def __unicode__(self):
        return _("Trail linking SMS ({sms}) with VumiLog ({vumi})").format(
            sms=self.sms.id if self.sms else None,
            vumi=self.vumi.id if self.vumi else None,
        )

    @property
    def direction(self):
        obj = self.sms or self.vumi
        return obj.direction

    def get_from(self):
        return (self.sms or self.vumi).from_number

    def get_to(self):
        return (self.sms or self.vumi).to_number

    @property
    def uuid(self):
        obj = self.sms or self.vumi
        return obj.uuid

    def clean(self):
        if not self.sms and not self.vumi:
            raise ValidationError("At least one of 'sms' or 'vumi' must be populated.")

    def report(self):
        vumi_url = self.vumi.get_absolute_url() if self.vumi else None
        sms_url = self.sms.get_absolute_url() if self.sms else None

        # Now build the report message
        if self.sms and self.vumi:
            msg = _('Audit complete. Message is in the <a href="{sms_url}">registration</a> '
                    'and <a href="{vumi_url}">gateway</a> systems.').format(
                        sms_url=sms_url,
                        vumi_url=vumi_url,
            )
        elif self.sms:
            msg = _('The <a href="{url}">message</a> to {number} with text "{text}" was '
                    'sent by the registration system at {datetime} but has not been '
                    'received by the gateway system.').format(
                        url=sms_url,
                        number=self.sms.to_number,
                        text=self.sms.message,
                        datetime=self.sms.creation_date,
            )
        else:
            msg = _('The <a href="{url}">message</a> from {number} with text "{text}" was '
                    'received by the gateway system at {datetime} but has not been '
                    'received by the registration system.').format(
                        url=vumi_url,
                        number=self.vumi.from_addr,
                        text=self.vumi.content,
                        datetime=self.vumi.logged_date,
            )
        return msg
    report.allow_tags = True


class Discrepancy(AbstractTimestampTrashBinModel):
    """
    Keeps track of SMSTrail objects that do not have both sms and vumi records.
    """
    trail = models.OneToOneField(SMSTrail, verbose_name=_('sms trail'))
    comments = models.TextField(_('comments'), blank=True)
    resolved = models.BooleanField(_('resolved'), blank=False, default=False)

    class Meta:
        permissions = [
            ('browse_discrepancy', _("Browse discrepancies")),
            ('read_discrepancy', _("Read discrepancy")),
        ]
        verbose_name = _("sms discrepancy")
        verbose_name_plural = _("sms discrepancies")
        ordering = ['-creation_date']

    def __unicode__(self):
        if self.trail.direction == INCOMING:
            msg = _("A discrepancy has been found for an incoming message at {datetime}.").format(
                datetime=self.creation_date)
        else:
            msg = _("A discrepancy has been found for an outgoing message at {datetime}.").format(
                datetime=self.creation_date)
        return msg

    def get_absolute_url(self):
        return reverse('read_discrepancy', args=(self.id,))

    def get_direction_display(self):
        return dict(VumiLog.DIRECTION_CHOICES)[self.trail.direction]

    def get_from(self):
        return self.trail.get_from()

    def get_to(self):
        return self.trail.get_to()

    def trail_report(self):
        return self.trail.report()
    trail_report.allow_tags = True

    def sms_as_html(self):
        return self.trail.sms_as_html

    def vumilog_as_html(self):
        return self.trail.vumilog_as_html
