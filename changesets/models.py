import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from civil_registry.models import Citizen
from libya_elections.abstract import AbstractTimestampModel
from register.models import RegistrationCenter, Registration

from .exceptions import NotPermittedToApprove, NotInApprovableStatus, NotApprovedBy, \
    NotAnAllowedStatus, ChangesetException


logger = logging.getLogger(__name__)


APPROVE_CHANGESET_PERMISSION = 'changesets.approve_changeset'
QUEUE_CHANGESET_PERMISSION = 'changesets.queue_changeset'
EDIT_CHANGESET_PERMISSION = 'changesets.change_changeset'
ADD_CHANGESET_PERMISSION = 'changesets.add_changeset'
READ_CHANGESET_PERMISSION = 'changesets.read_changeset'
BROWSE_CHANGESETS_PERMISSION = 'changesets.browse_changeset'
DELETE_CHANGESET_PERMISSION = 'changesets.delete_changeset'

CHANGE_CHANGESETS_GROUP = "Change Changesets"
APPROVE_CHANGESETS_GROUP = "Approve Changesets"
QUEUE_CHANGESETS_GROUP = "Queue Changesets"


class Changeset(AbstractTimestampModel):
    """
    Represent one atomic set of changes to registrations, such as moving citizens to
    a new center.
    """
    CHANGE_CENTER = 1
    CHANGE_BLOCK = 2
    CHANGE_UNBLOCK = 3
    CHANGE_ROLLBACK = 4
    CHANGE_CHOICES = [
        (CHANGE_CENTER, _("Move voters to another polling center")),
        (CHANGE_BLOCK, _("Block voters")),
        (CHANGE_UNBLOCK, _("Unblock voters")),
        (CHANGE_ROLLBACK, _("Roll back another changeset")),
    ]
    CHANGE_VALID_VALUES = [value for value, label in CHANGE_CHOICES]

    SELECT_CENTERS = 1
    SELECT_UPLOADED_NIDS = 2
    SELECT_OTHER_CHANGESET = 3
    HOW_TO_SELECT_CHOICES = [
        (SELECT_CENTERS, _("Select a list of polling centers")),
        (SELECT_UPLOADED_NIDS, _("Upload a list of national IDs")),
        (SELECT_OTHER_CHANGESET, _("Select another changeset")),
    ]

    # NB: Code relies on these statuses being in this order
    STATUS_NEW = 1
    STATUS_APPROVED = 2
    STATUS_QUEUED = 3
    STATUS_EXECUTING = 4
    STATUS_FAILED = 5
    STATUS_SUCCESSFUL = 6
    STATUS_PARTIALLY_SUCCESSFUL = 7
    STATUS_ROLLED_BACK = 8
    STATUS_CHOICES = [
        (STATUS_NEW, _("New - not approved")),
        (STATUS_APPROVED, _("Approved - not started")),
        (STATUS_QUEUED,
         _("Started - start button has been pressed but processing has not begun")),
        (STATUS_EXECUTING, _("Executing - being processed")),
        (STATUS_FAILED, _("Failed - had errors, changes were not made")),
        (STATUS_SUCCESSFUL, _("Successful - completed without errors and not rolled back")),
        (STATUS_PARTIALLY_SUCCESSFUL,
         _("Partially successful - rollback was not able to rollback all changes")),
        (STATUS_ROLLED_BACK, _("Rolled back - some or all changes have been rolled back")),
    ]
    # Changeset has finished executing, successfully or not
    HAS_BEEN_EXECUTED_STATUSES = [STATUS_SUCCESSFUL, STATUS_PARTIALLY_SUCCESSFUL, STATUS_FAILED,
                                  STATUS_ROLLED_BACK]
    # Changeset has been queued to be executed (or has been executed)
    HAS_BEEN_QUEUED_STATUSES = [STATUS_QUEUED, STATUS_EXECUTING] + HAS_BEEN_EXECUTED_STATUSES
    ROLLBACKABLE_STATUSES = [STATUS_SUCCESSFUL, STATUS_PARTIALLY_SUCCESSFUL]
    # Statuses in which it's okay to execute the changes
    EXECUTABLE_STATUSES = [STATUS_APPROVED, STATUS_QUEUED]

    name = models.CharField(_('name'), max_length=256, unique=True, blank=False)

    change = models.IntegerField(_('change'), choices=CHANGE_CHOICES, default=CHANGE_CENTER)

    how_to_select = models.IntegerField(
        _('how to select'),
        choices=HOW_TO_SELECT_CHOICES,
        default=SELECT_CENTERS,
        help_text=_("How to select affected voters. If you select another changeset, "
                    "it will change the same voters who were changed in the other changeset, "
                    "which might NOT be the same as using the same rules for selecting "
                    "voters that the other changeset used.")
    )

    other_changeset = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        verbose_name=_('other changeset'),
        related_name='target_changesets',
        help_text=_("Another changeset to select voters from or to roll back."),
        limit_choices_to={
            # Only allow selecting other changesets that have already been executed
            'status__in': HAS_BEEN_EXECUTED_STATUSES
        },
        on_delete=models.CASCADE
    )

    # The centers whose registrations we'll update
    selected_centers = models.ManyToManyField(
        RegistrationCenter,
        blank=True,
        verbose_name=_('selected centers'),
        related_name='changesets_from',
        limit_choices_to={
            # Don't require the source to support registrations at present, to allow moving
            # existing registrations away from such a center.
            'deleted': False,
        }
    )

    selected_citizens = models.ManyToManyField(
        'civil_registry.Citizen',
        blank=True,
        verbose_name=_('selected citizens'),
        related_name='changesets_selected',
    )

    target_center = models.ForeignKey(
        RegistrationCenter,
        null=True,
        blank=True,
        verbose_name=_('target center'),
        related_name='changesets_to',
        limit_choices_to={
            'reg_open': True,
            'deleted': False,
        },
        on_delete=models.PROTECT
    )

    message = models.CharField(
        _('message'),
        max_length=1024,
        default='',
        blank=True,
        help_text=_("Optional text message to send to affected voters after applying change"),
    )

    justification = models.TextField(
        _('justification'),
        help_text=_("Reason for the changes. Include references to legal justification "
                    "for the changes if possible.")
    )

    approvers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name=_('approvers'),
        related_name='changeset_approvals',
    )

    execution_start_time = models.DateTimeField(
        _('start time'),
        null=True, blank=True, editable=False,
        help_text=_("When execution of the changeset started.")
    )
    finish_time = models.DateTimeField(_('finish time'), null=True, blank=True, editable=False)

    queued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        verbose_name=_('queued by'),
        related_name='changesets_queued',
        help_text=_("The user who queued the changeset for execution."),
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name=_('created by'),
        related_name='changesets_created',
    )

    status = models.IntegerField(
        _('status'),
        choices=STATUS_CHOICES,
        default=STATUS_NEW,
    )

    rollback_changeset = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        verbose_name=_('rollback changeset'),
        help_text=_("If this changeset has been rolled back, this is the changeset that did it."),
        on_delete=models.PROTECT
    )

    error_text = models.TextField(
        _('error text'),
        blank=True,
        default='',
        help_text=_("If the changes failed, this will contain the error message(s).")
    )

    class Meta:
        verbose_name = _("changeset")
        verbose_name_plural = _("changesets")
        # Most recent changeset first
        ordering = ['-creation_date']
        # Custom permissions for approving and starting changesets.
        # With Django 1.7, these are actually created during migrations if we add new ones
        # here, yay!
        permissions = [
            ('approve_changeset', _("Approve changeset")),
            ('queue_changeset', _("Start changeset")),
            ('browse_changeset', _("Browse changesets")),
            ('read_changeset', _("Read changeset")),
        ]

    def clean(self):
        if (self.change == Changeset.CHANGE_ROLLBACK
                and self.how_to_select != Changeset.SELECT_OTHER_CHANGESET):
            raise ValidationError("Rollbacks must have how_to_select=OTHER CHANGESET")
        if (self.how_to_select == Changeset.SELECT_OTHER_CHANGESET
                and not self.other_changeset):
            raise ValidationError("how_to_select is SELECT_OTHER_CHANGESET but you have not "
                                  "selected another changeset.")

    @property
    def number_of_approvals(self):
        if self.pk:
            return self.approvers.count()
        return 0

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('read_changeset', args=[self.pk])

    def user_chooses_select_method(self):
        """True if the change type is one that lets the user choose a select method,
        e.g. SELECT_CENTERS"""
        return self.change != Changeset.CHANGE_ROLLBACK

    # Statuses:
    def has_been_queued(self):
        """Changeset has been queued to be executed at some point."""
        return self.status in Changeset.HAS_BEEN_QUEUED_STATUSES

    def has_been_executed(self):
        """Changeset has finished being executed, successfully or not."""
        return self.status in Changeset.HAS_BEEN_EXECUTED_STATUSES

    def in_editable_status(self):
        """True if the changeset can still be edited. (Once it's been started, it can't.)"""
        return not self.has_been_queued()

    def in_approvable_status(self):
        return self.in_editable_status()

    def in_queueable_status(self):
        """True if the changeset can be queued to be executed."""
        return self.status == Changeset.STATUS_APPROVED

    def in_executable_status(self):
        return self.status in Changeset.EXECUTABLE_STATUSES

    def in_rollbackable_status(self):
        return self.status in Changeset.ROLLBACKABLE_STATUSES

    def in_deletable_status(self):
        """Cannot delete once it has been queued"""
        return not self.has_been_queued()

    # Other information:
    def is_approved_by(self, user):
        return self.approvers.filter(pk=user.pk).exists()

    def number_affected(self):
        if self.has_been_executed():
            return self.change_records.filter(changed=True).count()
        else:
            return self.get_citizens_to_change().count()

    def number_not_changed(self):
        """Return the number of changes we were not able to make or undo"""
        return self.change_records.filter(changed=False).count()

    # Permissions:
    def may_be_edited_by(self, user):
        return user.has_perm(EDIT_CHANGESET_PERMISSION)

    def may_be_queued_by(self, user):
        return user.has_perm(QUEUE_CHANGESET_PERMISSION)

    def may_be_deleted_by(self, user):
        return user.has_perm(DELETE_CHANGESET_PERMISSION)

    def may_be_approved_by(self, user):
        return user.has_perm(APPROVE_CHANGESET_PERMISSION)

    # Actions
    def approve(self, user):
        """
        If the user is allowed and the changeset is in an acceptable state, add the
        user's approval.
        If that gets us to the minimum approvals, update the changeset to approved state.
        """
        if not self.may_be_approved_by(user):
            raise NotPermittedToApprove
        if not self.in_approvable_status():
            raise NotInApprovableStatus
        if not self.is_approved_by(user):
            self.approvers.add(user)
        if self.status < Changeset.STATUS_APPROVED \
                and self.number_of_approvals >= settings.MINIMUM_CHANGESET_APPROVALS:
            self.status = Changeset.STATUS_APPROVED
            self.save()

    def revoke_approval(self, user):
        """
        If the changeset is still in a state where approvals may be changed, and
        the user was an approver, remove their approval.
        If that makes the changeset no longer have the minimum number of approvals,
        update its state.
        """
        if not self.in_approvable_status():
            raise NotInApprovableStatus
        if not self.is_approved_by(user):
            raise NotApprovedBy
        self.approvers.remove(user)
        if self.status == Changeset.STATUS_APPROVED \
                and self.number_of_approvals < settings.MINIMUM_CHANGESET_APPROVALS:
            self.status = Changeset.STATUS_NEW
            self.save()

    def get_registrations_to_change(self):
        """
        Return a queryset of the Registration objects that should be
        changed, or whose citizens should be changed, for this changeset.
        """
        if self.how_to_select == Changeset.SELECT_CENTERS:
            # Get registrations from selected centers
            regs = Registration.objects.filter(registration_center__in=self.selected_centers.all())
            # Only include those that have citizen records
            citizens = Citizen.objects.filter(pk__in=regs.values_list('citizen_id', flat=True))
            citizen_ids = list(citizens.values_list('civil_registry_id', flat=True))
            regs = regs.filter(citizen_id__in=citizen_ids)
            return regs
        else:
            return Registration.objects.filter(citizen__in=self.get_citizens_to_change())

    def get_citizens_to_change(self):
        """
        Return a queryset of the citizen objects that should be changed,
        or whose registrations should be changed, for this changeset.
        """
        if self.how_to_select == Changeset.SELECT_UPLOADED_NIDS:
            return self.selected_citizens.all()

        if self.how_to_select == Changeset.SELECT_OTHER_CHANGESET:
            # Return citizens who were changed in another changeset
            changes = self.other_changeset.change_records.filter(changed=True)
            return Citizen.objects.filter(change_records__in=changes)

        if self.how_to_select == Changeset.SELECT_CENTERS:
            # Return citizens with registrations in selected centers
            registrations = self.get_registrations_to_change()
            return Citizen.objects.filter(registrations__in=registrations)

        raise NotImplementedError(
            "get_citizens_to_change not implemented for `how_to_select` value %d"
            % self.how_to_select)

    def queue(self):
        """Queue the changeset to be executed in the background."""
        if not self.in_queueable_status():
            raise NotAnAllowedStatus("Cannot start changeset in status %s"
                                     % self.get_status_display())
        self.status = Changeset.STATUS_QUEUED
        self.save()
        try:
            execute_changeset.delay(self.pk)
        except Exception:
            # If anything goes wrong scheduling the task,
            # un-mark the changeset as started
            self.status = Changeset.STATUS_APPROVED
            self.save()
            raise

    def execute(self):
        """
        Implement the changeset.

        If the changeset status is not valid to execute it,
        raise ChangesetException.

        Otherwise, try to execute the changeset and at the end, set the
        changeset status appropriately.

        Create ChangeRecords to record successful changes, and changes that
        might have been made but were not due to the current status of the
        affected citizen or registration (e.g., if in a rollback, the citizen
        is no longer in the status the changeset being rolled back left them
        in. Or in a block or unblock, if the citizen is already in the status
        the changeset was supposed to change them to).

        If the status is failed, no registration changes will have been
        applied (they are rolled back if needed).
        """

        logger.info("Execute changeset %s...", self.name)
        if not self.in_executable_status():
            raise NotAnAllowedStatus("Cannot execute changeset in status %s"
                                     % self.get_status_display())
        if self.change == Changeset.CHANGE_ROLLBACK:
            # Can only rollback a successful or partially successful changeset
            if not self.other_changeset.in_rollbackable_status():
                raise NotAnAllowedStatus("Cannot rollback changeset in status %s"
                                         % self.other_changeset.get_status_display())
        if self.change not in Changeset.CHANGE_VALID_VALUES:
            raise ChangesetException("Cannot execute changeset, %s is not a valid change type",
                                     self.change)
        try:
            self.status = Changeset.STATUS_EXECUTING
            self.execution_start_time = now()
            self.save()
            with transaction.atomic():
                if self.change == Changeset.CHANGE_CENTER:
                    changerecord_kwargs = dict(changeset=self, change=self.change,
                                               to_center=self.target_center)
                    # FIXME MAYBE: get_registrations_to_change() omits registrations that
                    # we're missing a citizen record on for some reason. So we could leave
                    # some registrations still pointing at the old center (albeit not
                    # valid registrations anymore).
                    for reg in self.get_registrations_to_change():
                        changerecord_kwargs.update(
                            citizen=reg.citizen,
                            from_center=reg.registration_center
                        )
                        if reg.registration_center == self.target_center:
                            # Citizen is already registered there.
                            # (Can happen if they uploaded a list of NIDs and later
                            # the citizen changed their registration.)
                            ChangeRecord.objects.create(changed=False, **changerecord_kwargs)
                        else:
                            reg.registration_center = self.target_center
                            reg.save_with_archive_version()
                            ChangeRecord.objects.create(changed=True, **changerecord_kwargs)
                elif self.change in [Changeset.CHANGE_BLOCK, Changeset.CHANGE_UNBLOCK]:
                    changerecord_kwargs = dict(changeset=self, change=self.change)
                    for citizen in self.get_citizens_to_change():
                        changerecord_kwargs['citizen'] = citizen
                        if self.change == Changeset.CHANGE_BLOCK and not citizen.blocked:
                            citizen.block()
                            ChangeRecord.objects.create(changed=True, **changerecord_kwargs)
                        elif self.change == Changeset.CHANGE_UNBLOCK and citizen.blocked:
                            citizen.unblock()
                            ChangeRecord.objects.create(changed=True, **changerecord_kwargs)
                        else:
                            ChangeRecord.objects.create(changed=False, **changerecord_kwargs)
                elif self.change == Changeset.CHANGE_ROLLBACK:
                    # Undo the changes made in another changeset, where possible
                    for change in ChangeRecord.objects.filter(changeset=self.other_changeset,
                                                              changed=True):
                        change.undo(self)
                    self.other_changeset.rollback_changeset = self
                    self.other_changeset.status = Changeset.STATUS_ROLLED_BACK
                    self.other_changeset.save()

                # Set the status depending on whether we applied all the requested changes
                if ChangeRecord.objects.filter(changeset=self, changed=False).exists():
                    self.status = Changeset.STATUS_PARTIALLY_SUCCESSFUL
                else:
                    self.status = Changeset.STATUS_SUCCESSFUL
                self.finish_time = now()
                self.save()
                logger.info("Changeset execution status: %s", self.get_status_display())
        except Exception as e:
            # Exiting the inner 'with transaction' by an exception will have triggered a rollback.
            # This log command will log the exception
            logger.exception("Executing changeset %s failed unexpectedly", self.name)
            self.status = Changeset.STATUS_FAILED
            self.error_text = str(e)
            self.finish_time = now()
            self.save()


class ChangeRecord(AbstractTimestampModel):
    """
    Record that a specific change was or was not made as part of a changeset.
    """
    # Note: some of this information is redundant with a forward
    # changeset (e.g. we could just look up the change type or
    # target center in the changeset), but it's not if this is
    # recording a rollback because the rollback changeset doesn't
    # have that information in it.
    changed = models.BooleanField(_('changed'), default=True, help_text="Whether change was made")
    changeset = models.ForeignKey(
        Changeset,
        verbose_name=_('changeset'),
        related_name='change_records',
        on_delete=models.PROTECT
    )
    citizen = models.ForeignKey(
        'civil_registry.Citizen',
        verbose_name=_('citizen'),
        related_name='change_records',
        on_delete=models.PROTECT,
    )
    change = models.IntegerField(
        _('change'),
        choices=Changeset.CHANGE_CHOICES
    )
    from_center = models.ForeignKey(
        RegistrationCenter,
        null=True,
        blank=True,
        verbose_name=_('from center'),
        related_name='changes_made_from',
        on_delete=models.PROTECT
    )
    to_center = models.ForeignKey(
        RegistrationCenter,
        null=True,
        blank=True,
        verbose_name=_('to center'),
        related_name='changes_made_to',
        on_delete=models.PROTECT
    )

    class Meta:
        permissions = [
            ('browse_changerecord', 'Browse changerecords'),
        ]
        verbose_name = _("change record")
        verbose_name_plural = _("change records")
        unique_together = [
            # We can only change a citizen once per changeset
            ('changeset', 'citizen'),
        ]
        ordering = ['change', 'changeset_id', 'citizen_id']

    def undo(self, changeset):
        """
        As part of `changeset`, try to undo this change. Create a new ChangeRecord
        to record what happened.
        """
        # Can't undo in the same changeset
        assert changeset != self.changeset
        # Can't undo something we didn't do
        assert self.changed

        changed = False
        citizen = self.citizen
        kwargs = dict(citizen=citizen, changeset=changeset)
        if self.change == Changeset.CHANGE_CENTER:
            kwargs.update(
                change=Changeset.CHANGE_CENTER,
                from_center=self.to_center,
                to_center=self.from_center,
            )
            try:
                # Only undo if they have a confirmed registration in
                # the center that the other changeset moved them to.
                current_registration = Registration.objects.get(citizen=citizen,
                                                                registration_center=self.to_center
                                                                )
            except Registration.DoesNotExist:
                pass
            else:
                current_registration.registration_center = self.from_center
                current_registration.save_with_archive_version()
                changed = True
        elif self.change == Changeset.CHANGE_BLOCK:
            kwargs['change'] = Changeset.CHANGE_UNBLOCK
            # Are they still blocked?
            if citizen.blocked:
                citizen.unblock()
                changed = True
        elif self.change == Changeset.CHANGE_UNBLOCK:
            kwargs['change'] = Changeset.CHANGE_BLOCK
            # Are they still unblocked?
            if not citizen.blocked:
                citizen.block()
                changed = True
        else:
            raise ChangesetException("Don't know how to undo change %s" % (self.change))
        # Make a record of what we did or didn't do
        ChangeRecord.objects.create(changed=changed, **kwargs)

    # Help with display
    def changed_yes_no(self):
        return _('Yes') if self.changed else _('No')

    def display_from_center(self):
        if self.change == Changeset.CHANGE_CENTER:
            return self.from_center

    def display_to_center(self):
        if self.change == Changeset.CHANGE_CENTER:
            return self.to_center


# Put at end to work around Python circular import but still be
# able to patch this in tests
from .tasks import execute_changeset  # noqa: E402
