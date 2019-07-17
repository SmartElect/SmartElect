# Django imports
from django.forms import DateInput, DateField, TimeField, TimeInput

# Project imports
from libya_elections.constants import LIBYA_DATE_FORMAT


DATE_FORM_FORMAT = LIBYA_DATE_FORMAT
DATE_INPUT_FORMATS = [DATE_FORM_FORMAT]
TIME_FORM_FORMAT = '%H:%M'
TIME_INPUT_FORMATS = [TIME_FORM_FORMAT]


class DateInputWithPicker(DateInput):
    """Date input widget that will get a jQuery-UI datepicker.

    The datepicker won't appear unless the following entries are added to the template:

    {% block extra_css %}
      <link href="{% static 'css/jquery/jquery-ui.min.css' %}" type="text/css" rel="stylesheet">
    {% endblock extra_css %}

    {% block extra_js %}
      <script type="text/javascript" src="{% static 'js/jquery/jquery-ui.min.js' %}"></script>
      <script type="text/javascript" src="{% static 'js/jquery/datepicker_apply.js' %}"></script>
      {% if LANGUAGE_CODE == 'ar' %}
        <script type="text/javascript" src="{% static 'js/jquery/datepicker_arabicize.js' %}">
        </script>
      {% endif %}
    {% endblock extra_js %}
    """
    def __init__(self, *args, **kwargs):
        kwargs['format'] = kwargs.get('format', DATE_FORM_FORMAT)
        super(DateInputWithPicker, self).__init__(*args, **kwargs)
        if 'class' not in self.attrs:
            self.attrs['class'] = ''

        self.attrs['class'] += ' wants_datepicker'


class DateFieldWithPicker(DateField):
    """A Django date form field that automatically uses a DateInputWithPicker widget."""
    def __init__(self, *args, **kwargs):
        input_formats = kwargs.pop('input_formats', DATE_INPUT_FORMATS)
        kwargs['widget'] = DateInputWithPicker()

        super(DateFieldWithPicker, self).__init__(*args, input_formats=input_formats, **kwargs)


class TimeInputWithPicker(TimeInput):
    """Date input widget that will get a jQuery-UI-based timepicker.

    The timepicker is by Jon Thornton - http://jonthornton.github.com/jquery-timepicker/

    The constructor accepts a kwarg of element_attributes. Key/value pairs in the element_attributes
    dict will be represented on the HTML element as attribute/value pairs. This is particularly
    useful for passing HTML5 'data-' attributes, e.g. 'data-time-format'.

    The datepicker won't appear unless the following entries are added to the template:

    {% block extra_css %}
      <link href="{% static 'css/jquery/timepicker.css' %}" type="text/css" rel="stylesheet">
    {% endblock extra_css %}

    {% block extra_js %}
      <script type="text/javascript" src="{% static 'js/jquery/jquery-ui.min.js' %}"></script>
      <script type="text/javascript" src="{% static 'js/jquery/timepicker.min.js' %}"></script>
      <script type="text/javascript" src="{% static 'js/jquery/timepicker_apply.js' %}"></script>
    {% endblock extra_js %}

    """
    def __init__(self, *args, **kwargs):
        kwargs['format'] = kwargs.get('format', TIME_FORM_FORMAT)
        element_attributes = kwargs.pop('element_attributes', {})

        super(TimeInputWithPicker, self).__init__(*args, **kwargs)
        if 'class' not in self.attrs:
            self.attrs['class'] = ''

        self.attrs['class'] += ' wants_timepicker'

        for name, value in element_attributes:
            self.attrs[name] = value


class TimeFieldWithPicker(TimeField):
    """A Django time form field that automatically uses a TimeInputWithPicker widget.

    The constructor accepts a kwarg of element_attributes. Key/value pairs in the element_attributes
    dict will be represented on the HTML element as attribute/value pairs. This is particularly
    useful for passing 'data-' attributes that can modify the timepicker control.

    For example, this creates a control in which the step size (see the timepicker doc) is set to
    43 minutes:
    TimeFieldWithPicker(element_attributes={'data-step':43})

    The Javascript of the timepicker uses PHP time formats (huh?). If you want to use a time
    format other than the default you need to pass it in two places and in two formats,
    e.g. for h:m:s --
    TimeFieldWithPicker(input_formats=['%I:%M:%S'],
                        element_attributes={'data-time-format': 'g:i:s'})

    See http://php.net/manual/en/function.date.php
    """
    def __init__(self, *args, **kwargs):
        input_formats = kwargs.pop('input_formats', TIME_INPUT_FORMATS)
        element_attributes = kwargs.pop('element_attributes', {})

        element_attributes['data-time-format'] = element_attributes.get('data-time-format', 'H:i')

        kwargs['widget'] = TimeInputWithPicker(element_attributes)

        super(TimeFieldWithPicker, self).__init__(*args, input_formats=input_formats, **kwargs)
