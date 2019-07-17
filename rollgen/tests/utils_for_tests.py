# -*- coding: utf-8 -*-
# Python imports
import io
import collections
import random
import os
import re
import sys
import time
from lxml import etree

# 3rd party imports
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.converter import XMLConverter
from pdfminer.layout import LAParams

# Project imports
# Importing pdf_canvas registers the fonts that the PDF will use.
import rollgen.pdf_canvas   # noqa
from ..utils import is_iterable

# Our PDFs use only Amiri-Regular and Amiri-Bold
EXPECTED_FONTS = ('Amiri-Regular', 'Amiri-Bold',)

ALEF_CANONICAL = '\u0627'
ALEF_ISOLATED = '\ufe8d'
NBSP = '\u00a0'
# Diacritics that need to be handled in swap_diacritics() (q.v.).
KASRA = '\u0650'
SHADDA = '\u0651'
FATHA = '\u064e'
DAMMA = '\u064f'
DIACRITIC_SWAP_REGEX = '(.[{}])'.format(''.join((KASRA, SHADDA, FATHA, DAMMA)))
DIACRITIC_SWAP_REGEX = re.compile(DIACRITIC_SWAP_REGEX, re.IGNORECASE)

# I use an explicit random seed so that if there's a bug in this run I can reproduce the
# bug by temporarily hardcoding the seed. I make the seed an int because floats are imperfectly
# represented by print, and I can't re-use the seed if I don't have an exact representation of it.
seed = int(time.time())
random.seed(seed)
# Writing to stderr ensures that if a test fails on Travis, the seed will be visible in Travis' log.
sys.stderr.write("seed is {}\n".format(seed))


def parse_bbox(bbox):
    """Given PDFMiner bbox info as a comma-delimited string, return it as a list of floats."""
    return list(map(float, bbox.split(',')))


def unwrap_lines(lines, index):
    """Combine the two lines at lines[index] and lines[index + 1].

    The actual lines extracted from the PDF sometimes contain long center and subcon names that
    have wrapped onto the following line. In most cases (generally on cover pages), that's not
    an error.

    However, my test code that builds the list of expected lines can't predict how and where the
    PDF layout algorithm will wrap a long name, so it always comes as somewhat of a surprise.

    It's easier to unwrap the actual lines than it is to figure out where to wrap the expected
    lines, and that's what this code does.
    """
    return lines[:index] + [lines[index + 1] + ' ' + lines[index]] + lines[index + 2:]


def clean_font_name(font_name):
    """Given a font name from PDFMiner's XML, return the font name with the "AAAAAA+" prefix
    removed (if present).
    """
    # For some reason font names have "AAAAAA+" or similar prepended, e.g. AAAAAA+Arial-BoldMT.
    # I've googled around but can't figure out the significance of this stuff.
    return font_name.split('+')[1] if ('+' in font_name) else font_name


def clean_textlines(textlines):
    """Given a list of textlines as from extract_textlines(), return a list of simple strings
    representing those textlines. Some artifacts of the text->PDF->text roundtrip are scrubbed.
    """
    lines = []
    for text_elements in textlines:
        line = ''.join([text_element.text for text_element in text_elements])
        line = normalize_alef(line)
        line = swap_diacritics(line)
        lines.append(line)

    return lines


def extract_pdf_page(filename, page_number_or_numbers):
    """Given the name of a PDF file and the pages to extract, use PDFMiner to extract those
    pages and return them as XML (in utf-8 bytes).

    The param page_number_or_numbers can be a single page number or an iterable thereof.
    """
    # This code adapted from pdf2txt.py which is part of PDFMiner.
    # Here's the command line version of the code below --
    #    pdf2txt.py -p 1 -o expected.xml sample.pdf

    if is_iterable(page_number_or_numbers):
        page_numbers = page_number_or_numbers
    else:
        page_numbers = [page_number_or_numbers]

    f_out = io.BytesIO()
    laparams = LAParams()
    rsrcmgr = PDFResourceManager()
    device = XMLConverter(rsrcmgr, f_out, codec='utf-8', laparams=laparams)

    with open(filename, 'rb') as f_in:
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        for page in PDFPage.get_pages(f_in, page_numbers):
            interpreter.process_page(page)

    device.close()

    xml = f_out.getvalue()
    f_out.close()

    return xml


def extract_textlines(xml):
    """Given XML (in bytes) output from PDFMiner, return a list of lists. The inner lists
    contain PDFMiner <text> elements (one character each) representing one line of text. The text
    elements are ordered as they appear left-to-right on the page. The inner lists themselves are
    sorted in the order that they appear top to bottom on the page.
    """
    # The text in PDFMiner's output is organized in <textline> elements which contain a bunch
    # of <text> elements. The <text> elements contain one character each. Both <textline> and
    # <text> elements have a bbox attr.
    #
    # Within a given textline, the ordering of the text subelements matches the left-to-right order
    # of the elements on the visible page.
    #
    # One might hope that the textline elements would appear in the XML in the same top-to-bottom
    # order that they appear on the visible page, but one so wishing would be disappointed. The
    # textline elements are not ordered in any obvious way.
    #
    # Furthermore, don't assume too much about what PDFMiner considers a "line". It seems logical
    # to me that if a set of text elements has the same y0/y1 values in their bbox attrs, they
    # would be contained in the same textline element. In practice, sometimes they are, and
    # sometimes they aren't.
    #
    # Perhaps that's because PDF permits layout where characters overlap horizontally and/or
    # vertically, and in that context it can be pretty difficult to decide what constitutes a
    # "line". Even our PDFs exhibit character overlap, because (for example) some Arabic letters
    # are represented in Unicode decomposed form. Decomposed form is diacritic + letter instead of
    # just the single (normalized) Unicode character that represents the two combined.
    # e.g. 0x654 + 0x627 (hamza + alef) versus 0x623 (Alef with hamza above)).
    #
    # The practical upshot is that we have to assemble the lines ourselves.

    # More info --
    #    The bbox value is (x0,y0,x1,y1).
    #
    #    x0: the distance from the left of the page to the left edge of the box.
    #    y0: the distance from the bottom of the page to the lower edge of the box.
    #    x1: the distance from the left of the page to the right edge of the box.
    #    y1: the distance from the bottom of the page to the upper edge of the box.
    #
    #    Remember in PDF the page origin is the *bottom left corner*.
    #    So the bottom left is (0,0) and the top right corner is
    #    somewhere like (612,792) in the case of A4 paper.
    #
    # Quoted from: https://groups.google.com/d/msg/pdfminer-users/wOvDSW23B4M/4fAWUhnrjO8J

    # My algorithm for constructing lines is as follows --
    #    Ignore the textline elements and throw all the text elements into a bucket
    #    Group them by bbox.y1
    #    Within each group, sort by (bbox.x0, bbox.x1)
    # Sorting by bbox.x0 alone is not sufficient when dealing with diacritics.
    root = etree.fromstring(xml)

    text_elements = root.xpath('.//text')

    # The dict lines_by_y_value groups text elements by bbox.y1 (they are the dict keys). Each
    # value in the dict is an unsorted list of 2-tuples of (text element, (bbox.x0, bbox.x1)).
    lines_by_y_value = collections.defaultdict(list)
    for text_element in text_elements:
        bbox = text_element.get('bbox')
        if bbox:
            x0, y0, x1, y1 = parse_bbox(text_element.get('bbox'))
            lines_by_y_value[y1].append((text_element, (x0, x1)))
        # else:
            # Some text elements (e.g. newlines) have no bbox info. I discard them.

    # Sort top to bottom
    y_values = sorted(lines_by_y_value.keys(), reverse=True)

    # Turn the dict into a sorted list of sorted lists.
    lines = []
    for y_value in y_values:
        line = lines_by_y_value[y_value]
        # Sort left-to-right
        line = sorted(line, key=lambda item: item[1])
        # I'm done with the bbox info so I can discard it now.
        line = [item[0] for item in line]
        lines.append(line)

    return lines


def extract_line_lengths(xml):
    """Given Unicode XML from PDFMiner, return a list of string lengths.

    The lengths are ordered in the same order as the strings in the PDF (first page to last,
    top to bottom of each page). The length unit (e.g. mm, em, inch, etc.) is whatever Reportlab
    uses as its default. The values are all in the same unit so they're comparable to one another.
    """
    lines = extract_textlines(xml)

    line_lengths = []

    for line in lines:
        # Each line is a list of PDFMiner <text> elements (one character each). I don't care
        # about the text, just the bbox info.
        character_bboxes = [parse_bbox(text_element.get('bbox')) for text_element in line]
        # length = (x1 of the last character) - (x0 of the first).
        line_lengths.append(character_bboxes[-1][2] - character_bboxes[0][0])

    return line_lengths


def _get_random_words(filename, n_words):
    """Given a # of words, return that many random words from the file 'filename'.

    If n_words > the number of words in the file, there will be duplicates in the list.

    This is a utililty function for get_random_arabic_citizen_names() and
    get_random_arabic_place_names().
    """
    words = open(filename, 'rb').read().decode('utf-8')
    # Remove blank lines and extraneous whitespace.
    words = [word.strip() for word in words.split('\n') if word.strip()]

    # There's only 267 names in that file and the caller may have asked for more which will
    # cause an error when random.sample() is called. I make sure I have enough n_names before I
    # call sample().
    while len(words) < n_words:
        words = words + words

    return random.sample(words, n_words)


def get_random_arabic_person_names(n_names):
    """Generate a list of Arabic names for use in creating fake person names.

    Given a # of names, returns a list of Arabic person names. Each will be a single name
    (e.g. just 'Muhammad', not 'Muhammad Mazin Habib'). If n_names > ~250, there will be
    duplicates in the list.
    """
    return _get_random_words(os.path.join('.', 'tests', '_random_arabic_person_names.txt'), n_names)


def get_random_arabic_place_names(n_names):
    """Generate a list of Arabic place names for use in creating fake place names.

    Given a # of names, returns a list of Arabic place names. These are real city names (e.g.
    London, Paris, Durham) in Arabic. If n_names > ~250, there will be duplicates in the list.
    """
    return _get_random_words(os.path.join('.', 'tests', '_random_arabic_place_names.txt'), n_names)


def generate_arabic_place_name(min_length=0):
    """Return a randomly generated, potentially multi-word fake Arabic place name"""
    make_name = lambda n_words: ' '.join(get_random_arabic_place_names(random.randint(1, n_words)))

    n_words = 3
    name = make_name(n_words)
    while len(name) < min_length:
        n_words += 1
        name = make_name(n_words)

    return name


def normalize_alef(s):
    """Given a string, replace Alef '\ufe8d' with Alef '\u0627'"""
    # For whatever reason, the initial/isolated Alef character ('\ufe8d') is reported by PDFMiner
    # as a canonical Alef '\u0627'. I don't know if it's Reportlab or PDFMiner that changes it from
    # one to the other. Since 0627 isn't in the Unicode section marked 'presentation forms' I don't
    # think it's supposed to be in the PDF at all, but whatever...
    # I don't know why the final Alef doesn't undergo a similar transformation.
    #
    # http://en.wikipedia.org/wiki/Arabic_alphabet#Letter_forms
    # '\u0627' = Alef isolated (same allograph as initial)
    # '\ufe8d' = Alef initial (same allograph as isolated)
    # '\ufe8e' = Alef final (same allograph as medial)
    return s.replace(ALEF_ISOLATED, ALEF_CANONICAL)


def swap_diacritics(s):
    """Given a string, return same with select Arabic diacritics swapped with left neighbor.

    Leading diacritics (i.e. in position 0) are unexpected and ignored by this code.
    """
    # In European languages, a letter with a diacritic is usually (always?) its own single Unicode
    # character. For instance, Swedish ö is Unicode 0xf6.
    #
    # Some (all?) Arabic diacritics are separate Unicode entities from their companion letters,
    # so a letter like ö can be represented in Arabic as two characters (umlaut + o). In the
    # PDF these two characters appear in the same bounding box so it is a bit ambiguous as to
    # which comes first when sorting left to right by x0/x1 coordinates.
    #
    # When I feed a sequence like abZd (where all the text is Arabic and Z is a diacritic) into the
    # PDF renderer, it comes back as aZbd which is not incorrect IMHO, but neither is abZd.
    # This function swaps the diacritics back around to the way I expect them.

    # The regex returns matches 2 character strings consisting of a diacritic and its left neighbor.
    # The lambda just returns that string in reverse (i.e. w/characters swapped).
    swap = lambda match: match.group()[::-1]
    return DIACRITIC_SWAP_REGEX.sub(swap, s)
