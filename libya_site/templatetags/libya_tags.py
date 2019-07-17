from django import template

from libya_elections.phone_numbers import formatted_phone_number_tag


register = template.Library()


@register.filter(name='format_phone_number')
def format_phone_number_tag(value):
    """
    Format a phone number, wrapped in a class which will be manipulated to
    display properly RTL or LTR.
    """
    return formatted_phone_number_tag(value)


@register.filter(name='getter')
def getter(value, arg):
    """
    Given an object `value`, return the value of the attribute named `arg`.
    `arg` can contain `__` to drill down recursively into the values.
    If the final result is a callable, it is called and its return
    value used.
    """
    if '__' in arg:
        # Get the value of the attribute name before the first '__', then
        # recursively call `getter` to get the rest.
        first_name, rest = arg.split('__', 1)
        if not hasattr(value, first_name):
            return 'No such field %r on %s' % (first_name, value)
        first_obj = getattr(value, first_name)
        result = getter(first_obj, rest)
    else:
        result = getattr(value, arg, 'No such field %r on %s' % (arg, value))
    if callable(result):
        result = result()
    return result
