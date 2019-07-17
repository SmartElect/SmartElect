from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import ugettext_lazy as _

from libya_elections.abstract import AbstractTimestampTrashBinModel
from libya_elections.constants import FIRST_PERIOD_NUMBER, LAST_PERIOD_NUMBER, NO_LINKED_OBJECT
from libya_elections.libya_bread import ElectionFormatterMixin, RegistrationCenterFormatterMixin
from libya_elections.phone_numbers import FormattedPhoneNumberMixin, format_phone_number
from libya_elections.utils import ensure_unique
from register.models import RegistrationCenter


class PollingReport(FormattedPhoneNumberMixin, ElectionFormatterMixin,
                    RegistrationCenterFormatterMixin, AbstractTimestampTrashBinModel):
    election = models.ForeignKey('voting.election', verbose_name=_('election'),
                                 on_delete=models.CASCADE)
    phone_number = models.CharField(_('phone number'),
                                    max_length=settings.MAX_PHONE_NUMBER_LENGTH,
                                    help_text=_("Received from this phone"))
    registration_center = models.ForeignKey(RegistrationCenter,
                                            verbose_name=_('registration center'),
                                            on_delete=models.CASCADE)
    period_number = models.IntegerField(
        _('period number'),
        validators=[
            MinValueValidator(FIRST_PERIOD_NUMBER),
            MaxValueValidator(LAST_PERIOD_NUMBER)
        ]
    )
    num_voters = models.IntegerField(
        _('number of voters'),
        validators=[
            MinValueValidator(0)
        ]
    )

    class Meta:
        verbose_name = _("polling report")
        verbose_name_plural = _("polling reports")
        permissions = (
            ("read_pollingreport", _("Can read polling report")),
            ("browse_pollingreport", _("Can browse polling reports")),
        )
        ordering = ['election_id', 'registration_center__center_id', '-period_number',
                    '-modification_date', ]


class CenterOpen(FormattedPhoneNumberMixin, ElectionFormatterMixin,
                 RegistrationCenterFormatterMixin, AbstractTimestampTrashBinModel):
    election = models.ForeignKey('voting.election', verbose_name=_('election'),
                                 on_delete=models.CASCADE)
    phone_number = models.CharField(_('phone number'),
                                    max_length=settings.MAX_PHONE_NUMBER_LENGTH,
                                    help_text=_("Received from this phone"))
    registration_center = models.ForeignKey(RegistrationCenter,
                                            verbose_name=_('registration center'),
                                            on_delete=models.CASCADE)

    class Meta:
        verbose_name = _("center open record")
        verbose_name_plural = _("center open records")
        permissions = (
            ("read_centeropen", _("Can read center open record")),
            ("browse_centeropen", _("Can browse center open record")),
        )
        ordering = ['election_id', 'registration_center__center_id', ]


class StaffPhone(FormattedPhoneNumberMixin, RegistrationCenterFormatterMixin,
                 AbstractTimestampTrashBinModel):
    phone_number = models.CharField(_('phone number'),
                                    max_length=settings.MAX_PHONE_NUMBER_LENGTH)
    registration_center = models.ForeignKey(RegistrationCenter,
                                            verbose_name=_('registration center'),
                                            on_delete=models.CASCADE)

    def __str__(self):
        try:
            rc = str(self.registration_center)
        except RegistrationCenter.DoesNotExist:
            rc = NO_LINKED_OBJECT
        return _('this staff phone {phone} from {center}').format(
            center=rc, phone=format_phone_number(self.phone_number)
        )

    def clean(self):
        ensure_unique(self._meta.model, self, 'phone_number')

    class Meta:
        verbose_name = _("staff phone")
        verbose_name_plural = _("staff phones")
        permissions = (
            ("read_staffphone", _("Can read staff phone")),
            ("browse_staffphone", _("Can browse staff phones")),
        )
        ordering = ['registration_center__center_id', '-modification_date']


class PreliminaryVoteCount(FormattedPhoneNumberMixin, ElectionFormatterMixin,
                           RegistrationCenterFormatterMixin, AbstractTimestampTrashBinModel):
    election = models.ForeignKey('voting.election', verbose_name=_('election'),
                                 on_delete=models.CASCADE)
    phone_number = models.CharField(_('phone number'), max_length=settings.MAX_PHONE_NUMBER_LENGTH,
                                    help_text=_("Received from this phone"))
    registration_center = models.ForeignKey(RegistrationCenter,
                                            verbose_name=_('registration center'),
                                            on_delete=models.CASCADE)
    # PositiveSmallIntegerField allows 0, so add a validator to require
    # it to be at least 1.
    option = models.PositiveSmallIntegerField(_('option'), validators=[MinValueValidator(1)])
    # Note: despite its name, PositiveIntegerField allows values of 0 and up
    num_votes = models.PositiveIntegerField(_('number of votes'), )

    class Meta:
        verbose_name = _("preliminary vote count")
        verbose_name_plural = _("preliminary vote counts")
        ordering = ['election', 'registration_center', 'option']
        permissions = (
            ("read_preliminaryvotecount", _("Can read preliminary vote count")),
            ("browse_preliminaryvotecount", _("Can browse preliminary vote counts")),
        )


class CenterClosedForElection(ElectionFormatterMixin, RegistrationCenterFormatterMixin,
                              AbstractTimestampTrashBinModel):
    # This model is used to note that a RegistrationCenter is/was inactive for a
    # particular election.
    election = models.ForeignKey('voting.election', verbose_name=_('election'),
                                 on_delete=models.CASCADE)
    registration_center = models.ForeignKey(RegistrationCenter,
                                            verbose_name=_('registration center'),
                                            on_delete=models.CASCADE)

    def __str__(self):
        return _('{center} closed for {election}').format(
            center=self.registration_center, election=self.election
        )

    class Meta:
        verbose_name = _("center closed for election")
        verbose_name_plural = _("centers closed for election")
        permissions = (
            ("read_centerclosedforelection", _("Can read center closed for an election")),
            ("browse_centerclosedforelection", _("Can browse centers closed for an election")),
        )
        ordering = ['election_id', 'registration_center__center_id', ]
