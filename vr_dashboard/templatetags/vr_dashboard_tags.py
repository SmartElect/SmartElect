import datetime

from django import template
from django.utils.translation import ugettext as _

from libya_site.utils import intcomma
from reporting_api.constants import PRELIMINARY_VOTE_COUNTS

register = template.Library()


@register.simple_tag(name='active_if_lang')
def active_if_lang(request, language_code):
    """ Emit 'class="active"' if running in the specified language. """
    if language_code == request.LANGUAGE_CODE:
        return 'class="active"'
    else:
        return ''


@register.assignment_tag()
def assign_lookup(current, *args):
    """A version of lookup() that can be used with 'as'.

    For example:
       {% assign_lookup a_dict 'by_office' office 'v' as n_votes %}
    """
    return lookup(current, *args)


@register.simple_tag(name='lookup')
def lookup(current, *args):
    """ Look up data in a single hash or a series of nested hashes, using
    keys (possibly variables) specified in args.  Return the final value.

    The caller can add the additional arg 'intcomma' to format an integer result
    like the intcomma filter of humanize.

    Django templates don't support hash lookups with variable keys (such
    as when iterating over different age groups in table columns).

    In the following example, age and gender are template variables, and the
    dict data with an age key yields another dict keyed by gender.

    <p>Count by age and gender: {% lookup data age gender %}</p>

    The following variation will format the count like the intcomma filter of
    humanize:

    <p>Count by age and gender: {% lookup data age gender intcomma %}</p>

    If the keys were constant, the normal Django template support could be used:

    <p>Count by age and gender: {{ data.19.F }}</p>
    <p>Count by age and gender: {{ data.19.F|intcomma }}</p>
    """
    int_comma = False
    for arg in args:
        if arg == '':  # trailing empty string args passed when invocation uses ' as <var>'
            break
        if arg == 'intcomma':
            int_comma = True
            break  # force 'intcomma' to be the last arg, when used
        current = current[arg]
    if int_comma:
        return intcomma(current)
    else:
        return current


def js_time(date_string):
    """ Convert a YYYY-mm-dd string into a JavaScript expression which evaluates
        to UTC time (milliseconds since the epoch).
    """
    dt = datetime.datetime.strptime(date_string, '%Y-%m-%d')
    return 'Date.UTC(%d, %d, %d, 0, 0, 0)' % (dt.year, dt.month - 1, dt.day)


@register.simple_tag(name='gen_data_points')
def gen_data_points(request, js_var_name, table, xy_keys):
    """
    Convert the Python data points to JavaScript, with the following transformations:
    * time strings converted to JavaScript time via js_time()
    * subdivision labels resolved into a specific string to use

    :param js_var_name: name of JavaScript variable to be created
    :param table: Python list of dictionaries per subdivision, from Redis
    :param xy_keys: whether to name the plot pairs 'x' and 'y' or 'label' and 'value'
    :return: string containing JavaScript form of data points
    """
    if xy_keys == 'xy':
        x_label, y_label = 'x', 'y'
    else:
        x_label, y_label = 'label', 'value'
    js = ['var %s = [' % js_var_name]
    for subdivision in table:  # e.g., each region/office/etc.
        if isinstance(subdivision['label'], basestring):
            label = _(subdivision['label'])
        elif request.LANGUAGE_CODE == 'en' and 'english_name' in subdivision['label']:
            label = subdivision['label']['english_name']
        elif request.LANGUAGE_CODE == 'ar' and 'arabic_name' in subdivision['label']:
            label = subdivision['label']['arabic_name']
        else:
            label = _(subdivision['label']['name'])
        js.append('        {key: "%s", values: [' % label)
        for row in subdivision.get('points', []):
            date_str = row[0]
            count = row[1] if row[1] is not None else 0
            js.append('            {%s: %s, %s: %d},' %
                      (x_label, js_time(date_str), y_label, count))
        js.append('         ]')
        js.append('        },')
    js.append('    ];')
    return '\n'.join(js)


@register.simple_tag(name='gen_prelim_count_cells')
def gen_prelim_count_cells(options, counts):
    """
    :param options: list of possible vote options
    :param counts: either a dict of vote counts or a dict that contains one
    :return: table cells with each vote count for the region, office, whatever,
      substituting '-' when no votes were reported by the entity for a vote
      option
    """
    counts = counts.get(PRELIMINARY_VOTE_COUNTS, counts)
    output = []
    for option in options:
        number = counts.get(option)
        formatted_number = intcomma(number) if number else '-'
        output.append('<td>%s</td>' % formatted_number)
    return ''.join(output)


@register.filter
def percentagify(numerator, denominator):
    """Given a numerator and a denominator, return them expressed as a percentage.

    Return 'N/A' in the case of division by 0.
    """
    if denominator:
        return '{:04.2f}%'.format((numerator / denominator) * 100)
    else:
        return 'N/A'
