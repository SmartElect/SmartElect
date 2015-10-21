import datetime
from dateutil.relativedelta import relativedelta
from django import template
from django.core.paginator import EmptyPage
from django.template.defaultfilters import date as date_format_filter
from django.utils.timezone import now
from django.utils.translation import ugettext as _
from help_desk.forms import DATE_FORM_FORMAT


register = template.Library()


def build_page_link(request, page_number):
    """
    Returns a URL to go to the specified page.

    Actually, returns "?" plus a query string that includes any
    query string that was part of the current request, plus a
    page=N parameter, without duplicating the page=N parameter if
    the current request already had one.
    """
    # remove any old page number and add new page number
    query_dict = request.GET.copy()  # Get a mutable copy of the query dict
    if 'page' in query_dict:
        del query_dict['page']
    query_dict['page'] = page_number
    return '?' + query_dict.urlencode()


@register.simple_tag(takes_context=True)
def next_page_link(context):
    try:
        return build_page_link(context['request'], context['page_obj'].next_page_number())
    except EmptyPage:
        return ''


@register.simple_tag(takes_context=True)
def previous_page_link(context):
    try:
        return build_page_link(context['request'], context['page_obj'].previous_page_number())
    except EmptyPage:
        return ''


@register.inclusion_tag('help_desk/date_filters.html')
def date_filters(form_id, options=None, use_range=True):
    if not options:
        options = ('months', 'quarters', 'years')
    filters = {}
    date_format = DATE_FORM_FORMAT  # Expected for dates used in code
    today = now().date()
    single_day = relativedelta(days=1)
    single_month = relativedelta(months=1)
    single_year = relativedelta(years=1)

    if 'months' in options:
        filters[_('Past 12 Months')] = []
        from_date = today.replace(day=1) + single_month
        for __ in range(12):
            to_date = from_date
            from_date = to_date - single_month
            to_date = to_date - single_day
            filters[_('Past 12 Months')].append(
                (
                    date_format_filter(from_date, 'M Y'),  # displayed
                    from_date.strftime(date_format) if use_range else "",  # used in code
                    to_date.strftime(date_format)  # used in code
                ))
        filters[_('Past 12 Months')].reverse()

    if 'years' in options:
        filters[_('Years')] = []
        start = today.year - 3
        for year in range(start, start + 4):
            from_date = datetime.datetime(year, 1, 1)
            to_date = from_date + single_year - single_day
            filters[_('Years')].append(
                (
                    str(from_date.year),
                    from_date.strftime(date_format) if use_range else "",
                    to_date.strftime(date_format)
                ))

    if 'quarters' in options:
        filters[_('Quarters (Calendar Year)')] = []
        to_date = datetime.date(today.year - 1, 1, 1) - single_day
        for x in range(8):
            from_date = to_date + single_day
            to_date = from_date + relativedelta(months=3) - single_day
            filters[_('Quarters (Calendar Year)')].append(
                (
                    '%s %s' % ((x % 4) + 1, from_date.year),
                    from_date.strftime(date_format) if use_range else "",
                    to_date.strftime(date_format)
                ))

    return {'filters': filters, 'form_id': form_id}
