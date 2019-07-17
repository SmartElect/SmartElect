# Django imports
from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

# Project imports
from libya_elections.constants import ANCHOR_SNIPPET
from libya_elections.utils import get_comma_delimiter

register = template.Library()


@register.filter
def display_center_infos(center_infos):
    """Given a list of center info tuples, return that list as an HTML string formatted with links.
    This is a specialized filter for the job view. Given a list of 2-tuples of (center id, url),
    return a string of marked-safe HTML where each center id is wrapped in an <a> with href=the url.
    """

    html = []
    for center_id, url in center_infos:
        if url:
            html.append(format_html(ANCHOR_SNIPPET.format(url, center_id)))
        else:
            html.append(str(center_id))
    delimiter = get_comma_delimiter()
    return mark_safe(delimiter.join(html))


@register.filter
def center_anchor(center_id):
    """Given a center id, returns a string suitable for use as an HTML id attribute value"""
    return 'c{}'.format(center_id)
