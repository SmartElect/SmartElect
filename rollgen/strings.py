# Python imports
import os
import codecs

# Django imports
from django.conf import settings

# 3rd party imports
import yaml

# Project imports
from rollgen.arabic_reshaper import reshape


def normalize_newlines(a_string):
    """Given a string (can be Unicode or not), turns all newlines into '\n'."""
    return a_string.replace('\r\n', '\n').replace('\r', '\n')


def load_strings():
    strings_path = os.path.join(settings.PROJECT_ROOT, 'rollgen', 'arabic_strings', 'ar.yml')
    locale_file = codecs.open(strings_path, 'r', encoding='utf-8')
    locale_dict = yaml.safe_load(locale_file)
    locale_file.close()
    out_dict = {}
    for (key, string) in locale_dict.items():
        # reshape, to fix ligatures
        shaped = reshape(string)
        # Newlines have to be converted to <br/> for consumption by reportlab. First I have to
        # ensure that the newline characters are predictable in case they were changed as a result
        # of the file being edited on Windows.
        # The codecs module doc says, "...no automatic conversion of '\n' is done on reading and
        # writing."
        shaped = normalize_newlines(shaped)
        shaped = shaped.replace('\n', '<br/>')
        out_dict[key] = shaped
    return out_dict


STRINGS = load_strings()
