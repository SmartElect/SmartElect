# Tweak the default formatting of numbers.
# By default, NUMBER_GROUPING is disabled and THOUSAND_SEPARATOR is '.'
THOUSAND_SEPARATOR = ','
NUMBER_GROUPING = 3

# The *_FORMAT strings use the Django date format syntax,
# see http://docs.djangoproject.com/en/dev/ref/templates/builtins/#date
# The full month name is not used in Libya
DATE_FORMAT = 'Y/m/d'
TIME_FORMAT = 'H:i'
DATETIME_FORMAT = 'H:i Y/m/d'
YEAR_MONTH_FORMAT = 'Y/m'
MONTH_DAY_FORMAT = 'm/d'
SHORT_DATE_FORMAT = 'Y/m/d'
SHORT_DATETIME_FORMAT = 'H:i Y/m/d'
FIRST_DAY_OF_WEEK = 0  # Sunday
