# Python imports
from __future__ import division
from __future__ import unicode_literals
import logging

# 3rd party imports
from reportlab.platypus import Image, Paragraph, PageBreak, Table, Spacer
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4, landscape

# Django imports
from django.conf import settings

# Project imports
from .arabic_reshaper import reshape
from .pdf_canvas import NumberedCanvas, getArabicStyle, getHeaderStyle, getTableStyleThreeCol
from .pdf_canvas import cda_logo, hnec_logo, drawHnecLogo
from .strings import STRINGS
from .utils import chunker, format_name, CountingDocTemplate, build_copy_info, \
    truncate_center_name, out_of_disk_space_handler_context, GENDER_NAMES
from libya_elections.constants import MALE, FEMALE, UNISEX

logger = logging.getLogger(__name__)


def log_voters(verb, skipped_voters):
    """Given a list of voters to be skipped or re-added, records them in the log. The verb
    should be one of "skipping" or "re-adding".
    """
    skipped_voters = [str(skipped_voter.registrant_number) for skipped_voter in skipped_voters]
    logger.debug("{} registrant numbers {}".format(verb, ', '.join(skipped_voters)))


def station_name_range(station):
    """Given a station, return the first and last voters, with supporting text.

    For male and female stations, this returns a 2-item list of 3-items lists of
    [[first voter], [last voter]] where each voter is a list of
    [voter name, voter number, the Arabic word first/last].

    For unisex stations, this returns a 5-item list of 3-items lists. The outer list consists of
    [first male voter, last male voter, [], first female voter, last female voter]. Each inner
    list consists of [voter name, voter number, the Arabic words male/female first/last].

    The data returned is formatted for direct insertion into tables on PDF cover pages.
    """
    data = []
    if station.gender in (FEMALE, MALE):
        data = [[reshape(format_name(station.first_voter)),
                 str(station.first_voter.registrant_number),
                 STRINGS['first']],
                [reshape(format_name(station.last_voter)),
                 str(station.last_voter.registrant_number),
                 STRINGS['last']]
                ]
    elif station.gender == UNISEX:
        roll_women = filter(lambda voter: voter.gender == FEMALE, station.roll)
        roll_men = filter(lambda voter: voter.gender == MALE, station.roll)

        # get first and last by gender
        first_voter_m = roll_men[0]
        last_voter_m = roll_men[-1]

        first_voter_f = roll_women[0]
        last_voter_f = roll_women[-1]
        data = [[reshape(format_name(first_voter_m)), str(first_voter_m.registrant_number),
                 "%s %s" % (STRINGS['male'], STRINGS['first'])],
                [reshape(format_name(last_voter_m)), str(last_voter_m.registrant_number),
                 STRINGS['last']],
                [],
                [reshape(format_name(first_voter_f)), str(first_voter_f.registrant_number),
                 "%s %s" % (STRINGS['female'], STRINGS['first'])],
                [reshape(format_name(last_voter_f)), str(last_voter_f.registrant_number),
                 STRINGS['last']]
                ]
    else:
        # This should never happen.
        raise ValueError("""Invalid gender "{}" for station "{}".""".format(station.gender,
                                                                            station.number))

    return data


def draw_header(elements, header_string, center_info, styles, station, type):
    # We wrap the page header in a table because we want the header's gray background to extend
    # margin-to-margin and that's easy to do with a table + background color. It's probably possible
    # with Paragraphs alone, but I'm too lazy^w busy to figure out how.
    # It's necessary to wrap the table cell text in Paragraphs to ensure the base text direction
    # is RTL. See https://github.com/hnec-vr/libya-elections/issues/1197
    para_prefix = Paragraph(STRINGS['ed_list_header_prefix'], styles['InnerPageHeader'])
    para_header = Paragraph(header_string, styles['InnerPageHeader'])
    header = Table([[para_prefix], [para_header]], 15*cm, [16, 24])
    header.setStyle(getHeaderStyle())

    elements.append(header)
    elements += [Paragraph(center_info['gender'], styles['CenterInfo-Bold']),
                 Paragraph(center_info['number'], styles['CenterInfo']),
                 Paragraph(center_info['name_trunc'], styles['CenterInfo']),
                 ]
    if type == "book":
        elements.append(
            Paragraph("%s: %d" % (STRINGS['station_number'], station.number),
                      styles['StationNumber'])
        )
        elements.append(Spacer(5, 5))
    else:
        elements.append(Spacer(10, 10))


def draw_body(elements, data, registrations_per_page):
    """Generate 3 column table and append to elements.

    data contains table rows. First element must be the header.
    """
    # Entire table is 20cm so row height is 20/n_rows
    row_height = 20 / registrations_per_page

    # Wrap all cell text in Paragraphs to ensure base direction is is RTL.
    # See https://github.com/hnec-vr/libya-elections/issues/1197.
    # Some of the data is integer (such as voter registrant numbers). That's OK to put directly in
    # a table cell but not for Paragraphs so I have to convert them to Unicode first.
    table_body_cell_style = getArabicStyle()['TableCell']
    table_header_cell_style = getArabicStyle()['TableCellHeader']

    header_row = [Paragraph(cell, table_header_cell_style) for cell in data[0]]
    data = [[Paragraph(unicode(cell), table_body_cell_style) for cell in row] for row in data[1:]]
    data.insert(0, header_row)

    # Table columns must add up to 15 cm
    column_widths = [6, 7, 2]
    assert(sum(column_widths) == 15)
    column_widths = [column_width * cm for column_width in column_widths]
    table = Table(data, column_widths, row_height*cm)
    table.setStyle(getTableStyleThreeCol())
    elements.append(table)


def draw_footer(elements, gender_string, styles):
    elements.append(Paragraph(gender_string, styles['PageBottom']))
    elements.append(PageBreak())


def generate_pdf_station_sign(filename, station):
    """Write a sign for the given station to filename.

    Return the number of pages in the PDF (which is always 1 if things are working properly).
    """
    # set styles
    styles = getArabicStyle()

    # get strings
    gender_string = STRINGS[GENDER_NAMES[station.gender]]
    cover_string = STRINGS['ed_polling_sign_header']

    # cover page
    center_name = reshape(station.center.name)
    if station.gender == UNISEX:
        # Unisex centers have a couple of lines of extra info at the bottom, and if the center
        # name happens to be long enough to wrap to a new line, the sign will wrap to two pages.
        # We truncate the center name to avoid that.
        center_name = truncate_center_name(center_name)

    center_info = {
        'gender': '%s: %s' % (STRINGS['gender'], gender_string),
        'number': '%s: %d' % (STRINGS['center_number'], station.center.center_id),
        'name': '%s: %s' % (STRINGS['center_name'], center_name),
        'copy_info': build_copy_info(station.center),
    }
    station_info = "%s &nbsp;&nbsp; %d" % (STRINGS['station_number'], station.number)

    # name range table
    name_range_data = station_name_range(station)
    style = styles['NameRangeTableCell']
    name_range_data = [[Paragraph(cell, style) for cell in row] for row in name_range_data]
    # Table params:          data             column_widths            row_height
    name_range_table = Table(name_range_data, [11*cm, 2.4*cm, 2.4*cm], 1.1*cm)

    # create landscape docuemnt
    doc = CountingDocTemplate(filename, pagesize=landscape(A4), topMargin=1*cm, bottomMargin=1*cm)

    # all elements on single page
    elements = [
        Table([[Image(cda_logo(), width=1.71*cm, height=1.3*cm), '', Image(hnec_logo(), width=4*cm,
                height=1.3*cm)]],
              [4*cm, 10*cm, 4*cm], 2*cm),
        Spacer(30, 30),

        Paragraph(cover_string, styles['Title']),
        Spacer(12, 12),
        Paragraph(center_info['name'], styles['Title']),
        Spacer(12, 12),
        Paragraph(center_info['number'], styles['Title']),
        Spacer(12, 12),
        Paragraph(center_info['copy_info'], styles['TitleCopyInfo']),
        Spacer(12, 12),

        Paragraph(station_info, styles['SignStationNumber']),
        Spacer(56, 56),

        Paragraph(center_info['gender'], styles['Title']),
        Spacer(10, 10),

        Paragraph(STRINGS['names_range'], styles['SignNameRange']),
        name_range_table,
        PageBreak(),
    ]

    with out_of_disk_space_handler_context():
        doc.build(elements)

    return doc.n_pages


def generate_pdf_station_book(filename, station):
    """Write the registration book for the given station to filename.

    If station gender is unisex, adds page breaks between male and female

    Return the number of pages in the PDF.
    """
    center = station.center

    # set styles
    styles = getArabicStyle()

    # get strings
    gender_string = STRINGS[GENDER_NAMES[station.gender]]
    cover_string = STRINGS['ed_station_book_cover']
    header_string = STRINGS['ed_station_book_header']

    # cover page
    center_name = reshape(center.name)
    template = u'%s: %s / %s'
    subconstituency_name = reshape(center.subconstituency.name_arabic)
    params = (STRINGS['subconstituency_name'], center.subconstituency.id, subconstituency_name)
    subconstituency = template % params

    center_info = {
        'gender': u'%s: %s' % (STRINGS['gender'], gender_string),
        'number': u'%s: %d' % (STRINGS['center_number'], center.center_id),
        'name': u'%s: %s' % (STRINGS['center_name'], center_name),
        'name_trunc': u'%s: %s' % (STRINGS['center_name'], truncate_center_name(center_name)),
        'subconstituency': subconstituency,
        'copy_info': build_copy_info(center),
    }

    station_info = "%s &nbsp;&nbsp; %d" % (STRINGS['station_number'], station.number)

    # name range table for cover
    name_range_data = station_name_range(station)
    style = styles['NameRangeTableCell']
    name_range_data = [[Paragraph(cell, style) for cell in row] for row in name_range_data]
    # Table params:          data             column_widths            row_height
    name_range_table = Table(name_range_data, [11*cm, 2.4*cm, 2.4*cm], 1.5*cm)

    # create document
    doc = CountingDocTemplate(filename, pagesize=A4, topMargin=1*cm, bottomMargin=1*cm,
                              leftMargin=1.5*cm, rightMargin=2.54*cm)
    # elements, cover page first
    elements = [
        Image(hnec_logo(), width=10*cm, height=2.55*cm),
        Spacer(48, 48),

        Paragraph(cover_string, styles['Title']),
        Spacer(18, 18),

        Paragraph(center_info['gender'], styles['CoverInfo-Bold']),
        Paragraph(center_info['number'], styles['CoverInfo']),
        Paragraph(center_info['name'], styles['CoverInfo']),
        Paragraph(center_info['copy_info'], styles['CoverInfo']),
        Paragraph(center_info['subconstituency'], styles['CoverInfo']),
        Spacer(18, 18),

        Paragraph(station_info, styles['CoverStationNumber']),
        Spacer(60, 60),

        Paragraph(STRINGS['names_range'], styles['CoverNameRange']),
        Spacer(18, 18),
        name_range_table,
        PageBreak(),
    ]

    # skipped_voters holds voters that we need to re-add when we go over a page break
    skipped_voters = []
    unisex = False

    for page in chunker(station.roll, settings.ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_BOOK):
        data = [[STRINGS['voted'], STRINGS['the_names'], STRINGS['number']]]  # table header

        # hacks for simulating page break between genders in unisex stations
        # last_voter tracks the previous iteration's last voter so we can add a blank line
        # at the switch
        voter_count = 0
        last_voter = None

        for voter in page:
            # if unisex station, add pagebreak between genders

            if (station.gender == UNISEX) and last_voter and \
               (voter.gender != last_voter.gender):

                # simulate a page break by adding n_registrants_per_page - voter_count blank lines
                logger.debug("voter_count={}".format(voter_count))
                lines_left = settings.ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_BOOK - voter_count
                logger.debug("lines_left={}".format(lines_left))
                if not unisex:
                    for i in range(0, lines_left):
                        data.append([])
                unisex = True
                skipped_voters = page[voter_count:voter_count+lines_left]
                log_voters("skipping", skipped_voters)
                break
            if not unisex:
                data.append(['', reshape(format_name(voter)), voter.registrant_number])
            else:
                skipped_voters.append(page[voter_count])
            last_voter = voter
            voter_count += 1

        if len(data) > 1:
            draw_header(elements, header_string, center_info, styles, station, "book")
            draw_body(elements, data, settings.ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_BOOK)
            draw_footer(elements, gender_string, styles)

    if skipped_voters:
        data = [[STRINGS['voted'], STRINGS['the_names'], STRINGS['number']]]

        for voter in skipped_voters:
            data.append(['', reshape(format_name(voter)), voter.registrant_number])
        log_voters("re-adding", skipped_voters)
        draw_header(elements, header_string, center_info, styles, station, "book")
        draw_body(elements, data, settings.ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_BOOK)
        draw_footer(elements, gender_string, styles)

    with out_of_disk_space_handler_context():
        doc.build(elements, canvasmaker=NumberedCanvas, onLaterPages=drawHnecLogo)

    return doc.n_pages


def generate_pdf_center_list(filename, stations, gender):
    """Write station list for a given center/gender combination.

    All stations must be for the same center.

    Return the number of pages in the PDF.
    """
    # All stations must have the same center.
    center = stations[0].center
    center_id = center.center_id
    assert(all([station.center.center_id == center_id for station in stations]))

    # set styles
    styles = getArabicStyle()

    # get strings
    gender_string = STRINGS[GENDER_NAMES[gender]]
    cover_string = STRINGS['ed_center_list_cover']
    header_string = STRINGS['ed_center_list_header']

    # cover page
    center_name = reshape(center.name)

    template = u'%s: %s / %s'
    subconstituency_name = reshape(center.subconstituency.name_arabic)
    params = (STRINGS['subconstituency_name'], center.subconstituency.id, subconstituency_name)
    subconstituency = template % params
    center_info = {
        'gender': u'%s: %s' % (STRINGS['gender'], gender_string),
        'number': u'%s: %d' % (STRINGS['center_number'], center_id),
        'name': u'%s: %s' % (STRINGS['center_name'], center_name),
        'name_trunc': u'%s: %s' % (STRINGS['center_name'], truncate_center_name(center_name)),
        'subconstituency': subconstituency,
        'copy_info': build_copy_info(center),
    }

    # create document
    doc = CountingDocTemplate(filename, pagesize=A4, topMargin=1*cm, bottomMargin=1*cm,
                              leftMargin=1.5*cm, rightMargin=2.54*cm)

    # elements, cover page first
    elements = [
        Image(hnec_logo(), width=10*cm, height=2.55*cm),
        Spacer(48, 48),
        Paragraph(cover_string, styles['Title']),
        Spacer(18, 18),
        Paragraph(center_info['gender'], styles['CoverInfo-Bold']),
        Paragraph(center_info['number'], styles['CoverInfo']),
        Paragraph(center_info['name'], styles['CoverInfo']),
        Paragraph(center_info['copy_info'], styles['CoverInfo']),
        Paragraph(center_info['subconstituency'], styles['CoverInfo']),
        PageBreak(),
    ]

    roll = []
    for station in stations:
        if station.gender == gender:
            roll.extend(station.roll)
        else:
            # Coverage can't "see" the next line executed.
            continue  # pragma: no cover

        skipped_voters = []  # to re-add when we go over a page break
        unisex = False

        for page in chunker(station.roll, settings.ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_LIST):
            # table header
            data = [[STRINGS['station_header'], STRINGS['the_names'], STRINGS['number']]]

            # hacks for simulating page break between genders in unisex stations
            # last_voter tracks the previous iteration's last voter so we can add a blank line
            # at the switch
            last_voter = None
            voter_count = 0

            for voter in page:
                # if unisex station, add pagebreak between genders
                if (station.gender == UNISEX) and last_voter and \
                   (voter.gender != last_voter.gender):

                    # simulate a page break by adding N blank lines where
                    # N = ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_LIST - voter_count
                    logger.debug("voter_count={}".format(voter_count))
                    lines_left = settings.ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_LIST - voter_count
                    logger.debug("lines_left={}".format(lines_left))
                    if not unisex:
                        for i in range(0, lines_left):
                            data.append([])
                    unisex = True
                    skipped_voters = page[voter_count: voter_count + lines_left]
                    log_voters("skipping", skipped_voters)
                    break
                if not unisex:
                    data.append([station.number, reshape(format_name(voter)),
                                 voter.registrant_number])
                else:
                    skipped_voters.append(page[voter_count])
                last_voter = voter
                voter_count += 1

            if len(data) > 1:
                draw_header(elements, header_string, center_info, styles, station, "list")
                draw_body(elements, data, settings.ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_LIST)
                draw_footer(elements, gender_string, styles)

        if skipped_voters:
            data = [[STRINGS['station_header'], STRINGS['the_names'], STRINGS['number']]]

            for voter in skipped_voters:
                data.append([station.number, reshape(format_name(voter)),
                             voter.registrant_number])
            log_voters("re-adding", skipped_voters)
            draw_header(elements, header_string, center_info, styles, station, "list")
            draw_body(elements, data, settings.ROLLGEN_REGISTRATIONS_PER_PAGE_POLLING_LIST)
            draw_footer(elements, gender_string, styles)

    with out_of_disk_space_handler_context():
        doc.build(elements, canvasmaker=NumberedCanvas, onLaterPages=drawHnecLogo)

    return doc.n_pages
