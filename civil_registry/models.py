from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import QuerySet
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from libya_elections.constants import FEMALE, MALE
from libya_elections.libya_bread import BirthDateFormatterMixin


class CitizenManager(models.Manager):
    queryset = QuerySet
    use_for_related_fields = True

    def get_queryset(self):
        """Default queries return only unmissing objects."""
        return self.queryset(self.model, using=self._db).filter(missing=None)

    # For any old code that still calls `get_query_set`:
    get_query_set = get_queryset

    def unfiltered(self, using=None):
        """Return a qs of all objects, missing and not missing."""
        if not using:
            using = self._db
        return self.queryset(self.model, using=using).all()

    def missing(self):
        """Return a qs of all missing objects."""
        return self.unfiltered(using=self._db).exclude(missing=None)


# We create an abstract model and then inherit two
# concrete models from it so we can keep them exactly
# in sync as far as fields etc.
class AbstractCitizen(models.Model):
    """
    Mirrors a citizen's record in the civil registry
    (at least, as much of it as they will give us access to)

    This always contains the latest, current data (as best we can tell).
    There's no record kept here of past data, change history, etc.
    """
    GENDERS = (
        (FEMALE, 'Female'),
        (MALE, 'Male'),
    )
    GENDER_MAP = {k: v for k, v in GENDERS}

    # In order to avoid poor performance on the citizen browse view when sorting, we create an
    # index on each sortable field in that view.

    civil_registry_id = models.BigIntegerField(  # PERSON_ID in civil registry
        _('civil registry id'),
        help_text=_("Uniquely identifies a person, even across changes of national ID"),
        primary_key=True,
    )
    national_id = models.BigIntegerField(  # NATIONAL_ID in civil registry
        _('national id'),
        help_text=_("The citizen's 12-digit national ID number"),
        db_index=True,
        unique=True,
        validators=[
            MinValueValidator(100000000000),
            MaxValueValidator(299999999999),
        ]
    )
    fbr_number = models.BigIntegerField(  # REGISTRY_NO in civil registry
        _('family book record number'),
        help_text=_('Family Book Record Number')
    )
    first_name = models.CharField(_('first name'),              # NAME in civil registry
                                  db_index=True, max_length=255, blank=True)
    father_name = models.CharField(_('father name'),            # FATHER_NAME_AR in civil registry
                                   max_length=255, blank=True)
    grandfather_name = models.CharField(_('grandfather name'),  # GRANDFATHER_NAME_AR
                                        max_length=255, blank=True)
    family_name = models.CharField(_('family name'),            # FAM_NAME in civil registry
                                   db_index=True, max_length=255, blank=True)
    mother_name = models.CharField(_('mother name'),            # MOTHER_NAME_AR
                                   max_length=255, blank=True)
    birth_date = models.DateField(_('birth date'),              # DATE_OF_BIRTH in civil registry
                                  db_index=True)
    gender = models.IntegerField(_('gender'),                   # GENDER
                                 db_index=True, choices=GENDERS)
    address = models.CharField(_('address'), max_length=1024, blank=True)  # ADDRESS

    # We don't know what these are yet, but they're in the exported data
    # so let's keep track of them. They might be useful some day.
    office_id = models.IntegerField(_('office id'), default=0)  # OFFICE_ID
    branch_id = models.IntegerField(_('branch id'), default=0)     # BRANCH_ID
    state = models.IntegerField(_('state'), default=0)          # STATE

    missing = models.DateTimeField(
        _('missing'),
        null=True,
        blank=True,
        help_text=_("If set, this citizen was not in the last data dump."),
    )

    objects = CitizenManager()

    class Meta(object):
        abstract = True

    def format_name(self):
        """Returns the citizen's name formatted appropriately for display."""
        fields = ['first_name', 'father_name', 'grandfather_name', 'family_name']
        # ltr here, because bidi flips output
        return ' '.join([getattr(self, field) for field in fields])
    format_name.short_description = _('name')

    def __unicode__(self):
        return self.format_name()

    @property
    def gender_formatted(self):
        return self.GENDER_MAP[self.gender]


# Our actual citizen data
class Citizen(BirthDateFormatterMixin, AbstractCitizen):
    class Meta:
        verbose_name = _("citizen")
        verbose_name_plural = _("citizens")
        permissions = (
            ("read_citizen", "Can read citizens"),
            ("browse_citizen", "Can browse citizens"),
        )
        ordering = ['national_id']

    @cached_property
    def person(self):
        """Return the corresponding Person, creating one if needed"""
        from register.models import Person
        try:
            return Person.objects.get(citizen=self)
        except Person.DoesNotExist:
            return Person.objects.create_from_citizen(self)

    @property
    def has_person(self):
        # Determine if there's a person for this citizen, without
        # creating one as a side-effect like just referencing `.person`
        # would do.
        from register.models import Person
        return Person.objects.filter(citizen=self).exists()

    def block(self):
        self.person.block()

    def unblock(self):
        self.person.unblock()

    @property
    def blocked(self):
        return self.has_person and self.person.blocked

    @property
    def registration(self):
        """
        Return citizen's current valid registration, or None.
        """
        from register.models import Registration
        try:
            return self.registrations.get(deleted=False, archive_time=None)
        except Registration.DoesNotExist:
            return None

    def is_eligible(self, as_of=None):
        """
        Return True if user is eligible to register.
        as_of is optional datetime to check at that time.

        Currently checks that they're 18 years old as of today, and that
        they're not blocked. Other requirements could be added.
        """
        if self.blocked:
            return False
        # Uses a simple, traditional way to see if someone is N years old -
        # compare their birth date to today's date, with N subtracted from
        # the year.
        if as_of is None:
            as_of = now()
        today = as_of.date()
        # Express as (y, m, d)
        must_be_born_by = (today.year - settings.VOTING_AGE_IN_YEARS, today.month, today.day)
        birth = (self.birth_date.year, self.birth_date.month, self.birth_date.day)
        # Python lets us compare tuples directly - Python FTW!
        return birth <= must_be_born_by

    def get_absolute_url(self):
        return reverse('read_citizen', args=[self.civil_registry_id])


# Used during updating of our data
class TempCitizen(AbstractCitizen):
    """
    Subclass of Citizen just to make it easy to have a second model
    with exactly the same definition.
    """


class CitizenMetadata(models.Model):
    # The last time the data was updated.
    dump_time = models.DateTimeField()


class DumpFile(models.Model):
    """
    Represents a dump file provided to us by the CRA.

    Does not try to store where the file is, just the filenames
    we've seen before.
    """
    filename = models.CharField(max_length=256)
