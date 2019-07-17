from functools import total_ordering

from django.db import models
from django.db.models.query import QuerySet
from django.utils.formats import date_format
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _


@total_ordering
class AbstractBaseModel(models.Model):
    """Base class for all models in this project"""
    class Meta:
        abstract = True

    def __lt__(self, other):
        """Sort by PK"""
        # https://github.com/hnec-vr/libya-elections/issues/1130
        if isinstance(other, type(self)):
            return self.pk < other.pk
        else:
            return str(self) < str(other)


class TrashBinManager(models.Manager):
    queryset = QuerySet

    def get_queryset(self):
        """Default queries return only undeleted objects."""
        return self.queryset(self.model, using=self._db).filter(deleted=False)

    # For any old code that still calls `get_query_set`:
    get_query_set = get_queryset

    def unfiltered(self, using=None):
        """Return a qs of all objects, deleted and undeleted."""
        if not using:
            using = self._db
        return self.queryset(self.model, using=using).all()

    def deleted(self):
        """Return a qs of all deleted objects."""
        return self.unfiltered(using=self._db).filter(deleted=True)


class AbstractTrashBinModel(AbstractBaseModel):
    deleted = models.BooleanField(_('deleted'), default=False)

    objects = TrashBinManager()

    class Meta:
        abstract = True

    def soft_delete(self):
        """Set deleted=True. Does not explicitly change any other fields,
        though AbstractTimestampModel's save() will update modification_date too."""
        self.deleted = True
        self.save(update_fields=['deleted'])

    def _do_update(self, base_qs, using, pk_val, values, update_fields, forced_update):
        """
        Override superclass method to force use of the unfiltered queryset when
        trying to update records. Otherwise, Django uses the default manager
        (TrashBinManager) which filters out deleted records, making it
        impossible to update deleted records.
        """
        base_qs = self.__class__.objects.unfiltered(using=using)
        return super(AbstractTrashBinModel, self)._do_update(
            base_qs, using, pk_val, values, update_fields, forced_update)


class AbstractTimestampModel(AbstractBaseModel):
    creation_date = models.DateTimeField(_('creation date'), default=now, editable=False)
    modification_date = models.DateTimeField(_('modification date'), default=now, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.modification_date = now()
        # Make sure we save the updated modification_date, even if the save
        # call is using `update_fields`
        if 'update_fields' in kwargs and 'modification_date' not in kwargs['update_fields']:
            kwargs['update_fields'].append('modification_date')
        super(AbstractTimestampModel, self).save(*args, **kwargs)

    @property
    def formatted_creation_date(self):
        return date_format(self.creation_date, "SHORT_DATETIME_FORMAT")

    @property
    def formatted_modification_date(self):
        return date_format(self.modification_date, "SHORT_DATETIME_FORMAT")


class AbstractTimestampTrashBinModel(AbstractTimestampModel, AbstractTrashBinModel):
    class Meta:
        abstract = True


class ArchivableTrashBinManager(TrashBinManager):

    def get_queryset(self):
        """Default queries return only undeleted, unarchived objects."""
        return self.queryset(self.model, using=self._db).filter(deleted=False, archive_time=None)

    # For any old code that still calls `get_query_set`
    get_query_set = get_queryset

    def unfiltered(self, using=None):
        """Return a qs of all objects, deleted and undeleted, archived and not archived."""
        if not using:
            using = self._db
        return self.queryset(self.model, using=using).all()

    def archived(self, using=None):
        """Return a qs of all archived objects, deleted or not."""
        return self.unfiltered(using=using).exclude(archive_time=None)


class AbstractArchivableTimestampTrashBinModel(AbstractTimestampTrashBinModel):
    archive_time = models.DateTimeField(
        _('archive time'),
        default=None,
        null=True,
        blank=True,
        help_text=_("If non-NULL, from this time on, this record is no longer in effect.")
    )

    objects = ArchivableTrashBinManager()

    class Meta:
        abstract = True

    def save_with_archive_version(self):
        """
        Make an archive copy of what's currently in the database for this record,
        then save this one, updating the creation_date to indicate this version starts
        being valid now.
        """
        archive = type(self).objects.get(pk=self.pk)
        archive.pk = None
        archive.archive_time = now()
        archive.save()

        # Update this one's creation time as the archive record's archive time,
        # so there's a continuous time when one record or the other was valid.
        self.creation_date = archive.archive_time
        self.save()

    @property
    def formatted_archive_time(self):
        return date_format(self.archive_time, "SHORT_DATETIME_FORMAT") if self.archive_time else ''
