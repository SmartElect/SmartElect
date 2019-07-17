# 3rd party imports
from reportlab.platypus import Image, Paragraph, PageBreak, Table, Spacer
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4

# Django imports
from django.conf import settings

# Project imports
from .arabic_reshaper import reshape
from .pdf_canvas import NumberedCanvas, getArabicStyle, getHeaderStyle, getTableStyle, \
    get_hnec_logo_fname, drawHnecLogo
from .strings import STRINGS
from .utils import chunker, format_name, CountingDocTemplate, build_copy_info, \
    truncate_center_name, out_of_disk_space_handler_context
from libya_elections.constants import MALE, FEMALE


def generate_pdf(filename, center, voter_roll, gender, center_book=False):
    # filename: the file to which the PDF will be written
    # center: a data_pull.Center instance
    # voter_roll: list of registration dicts --
    #    {national_id, first_name, father_name, grandfather_name, family_name, gender}
    # gender: one of the MALE/FEMALE constants. UNISEX is not valid.
    # center_book: ???
    #
    # separates by gender code using one of the constants in utils.Gender
    # sorts by name fields in query
    # assembles display string from parts
    # writes to filename
    #
    # returns number of pages in the PDF

    if gender not in (MALE, FEMALE):
        raise ValueError("generate_pdf() gender must be MALE or FEMALE")

    # set styles
    styles = getArabicStyle()

    # get strings
    mf_string = STRINGS['female'] if (gender == FEMALE) else STRINGS['male']
    cover_string = STRINGS['center_book_cover'] if center_book else STRINGS['center_list_cover']
    header_string = STRINGS['center_book_header'] if center_book else STRINGS['center_list_header']

    # cover page
    center_name = reshape(center.name)

    template = '%s: %s / %s'
    subconstituency_name = reshape(center.subconstituency.name_arabic)
    params = (STRINGS['subconstituency_name'], center.subconstituency.id, subconstituency_name)
    subconstituency = template % params

    center_info = {
        'gender': '%s: %s' % (STRINGS['gender'], mf_string),
        'number': '%s: %d' % (STRINGS['center_number'], center.center_id),
        'name': '%s: %s' % (STRINGS['center_name'], center_name),
        'name_trunc': '%s: %s' % (STRINGS['center_name'], truncate_center_name(center_name)),
        'subconstituency': subconstituency,
        'copy_info': build_copy_info(center),
    }

    # create document
    doc = CountingDocTemplate(filename, pagesize=A4, topMargin=1 * cm, bottomMargin=1 * cm,
                              leftMargin=1.5 * cm, rightMargin=2.54 * cm)

    # elements, cover page first
    with open(get_hnec_logo_fname(), 'rb') as hnec_f:
        elements = [
            Image(hnec_f, width=10 * cm, height=2.55 * cm),
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

        # Focus on one specific gender.
        voter_roll = [voter for voter in voter_roll if voter.gender == gender]

        # We wrap the page header in a table because we want the header's gray background to extend
        # margin-to-margin and that's easy to do with a table + background color. It's probably
        # possible with Paragraphs alone, but I'm too lazy^w busy to figure out how.
        # It's necessary to wrap the table cell text in Paragraphs to ensure the base text direction
        # is RTL. See https://github.com/hnec-vr/libya-elections/issues/1197
        para_prefix = Paragraph(STRINGS['center_header_prefix'], styles['InnerPageHeader'])
        para_header = Paragraph(header_string, styles['InnerPageHeader'])
        page_header = Table([[para_prefix], [para_header]], 15 * cm, [16, 24])
        page_header.setStyle(getHeaderStyle())

        n_pages = 0
        for page in chunker(voter_roll, settings.ROLLGEN_REGISTRATIONS_PER_PAGE_REGISTRATION):
            n_pages += 1
            elements.append(page_header)
            elements += [Paragraph(center_info['gender'], styles['CenterInfo-Bold']),
                         Paragraph(center_info['number'], styles['CenterInfo']),
                         Paragraph(center_info['name_trunc'], styles['CenterInfo']),
                         ]
            elements.append(Spacer(10, 10))

            # The contents of each table cell are wrapped in a Paragraph to set the base text
            # direction.
            # See https://github.com/hnec-vr/libya-elections/issues/1197
            data = [[Paragraph(reshape(format_name(voter)), styles['TableCell'])] for voter in page]
            # Insert header before the data.
            data.insert(0, [Paragraph(STRINGS['the_names'], styles['TableCell'])])

            table = Table(data, 15 * cm, 0.825 * cm)
            table.setStyle(getTableStyle())
            elements.append(table)

            elements.append(Paragraph(mf_string, styles['PageBottom']))
            elements.append(PageBreak())

        if not n_pages:
            # When there are no pages (==> no registrants for this gender), we need to emit a page
            # that states that.
            elements.append(page_header)
            key = 'no_male_registrants' if gender == MALE else 'no_female_registrants'
            elements.append(Paragraph(STRINGS[key], styles['BlankPageNotice']))

        with out_of_disk_space_handler_context():
            doc.build(elements, canvasmaker=NumberedCanvas, onLaterPages=drawHnecLogo)

    return doc.n_pages
