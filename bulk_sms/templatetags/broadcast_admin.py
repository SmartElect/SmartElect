from __future__ import unicode_literals

from django import template
from django.utils.translation import ugettext as _

register = template.Library()


@register.inclusion_tag('admin/broadcast/submit_line.html', takes_context=True)
def approve_submit_row(context):
    """
    Displays the row of buttons for approve, delete, go back, reject and save.
    """
    opts = context['opts']
    change = context['change']
    is_popup = context['is_popup']
    save_as = context['save_as']
    if context['request'].user.is_superuser:
        delete_label = _('Permanently delete')
    else:
        delete_label = _('Delete')
    extra_context = {
        'opts': opts,
        'delete_label': delete_label,
        'preserved_filters': context.get('preserved_filters'),
        'show_delete_link': (not is_popup and context['has_delete_permission']
                             and change and context.get('show_delete', True)),
        'show_save_as_new': not is_popup and save_as and not change,
        'show_save_and_add_another': (context['has_add_permission'] and
                                      not is_popup and context['has_change_permission']),
        'show_save_and_continue': not is_popup and context['has_change_permission'],
        'show_go_back': context['has_read_permission'],
        'is_popup': is_popup,
        'show_save': context['has_change_permission'],
    }
    context.update(extra_context)
    return context
