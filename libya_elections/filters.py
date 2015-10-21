from django.db.models.fields import BLANK_CHOICE_DASH

from django_filters import ChoiceFilter


class LibyaChoiceFilter(ChoiceFilter):
    """A Single Choice Filter which adds a choice at the top signifying not to filter."""

    @property
    def field(self):
        self.extra['choices'] = BLANK_CHOICE_DASH + list(self.extra['choices'])
        return super(LibyaChoiceFilter, self).field
