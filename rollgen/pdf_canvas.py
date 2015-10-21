# Python imports
from __future__ import division
from __future__ import unicode_literals
import os

# Django imports
from django.conf import settings

# 3rd party imports
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm

from reportlab.lib.styles import StyleSheet1, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus import TableStyle
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ASSETS_PATH = os.path.join(settings.PROJECT_ROOT, 'rollgen', 'assets')
pdfmetrics.registerFont(TTFont('Arabic', os.path.join(ASSETS_PATH, 'amiri-regular.ttf')))
pdfmetrics.registerFont(TTFont('Arabic-Bold', os.path.join(ASSETS_PATH, 'amiri-bold.ttf')))

# TABLE_FONT_SIZE controls the font size for table body text.
TABLE_FONT_SIZE = 14


class NumberedCanvas(canvas.Canvas):
    # numbered canvas class that works with embedded images
    # modified from http://code.activestate.com/recipes/576832/
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        """add page info to each page (page x of y)"""
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        if self._pageNumber > 1:
            self.setFont("Arabic", 10)
            # The page # args are backwards to what one might expect because of RTL.
            # Subtract 1, because we're not counting cover
            self.drawCentredString(A4[0]/2, 10*mm,
                                   "%d / %d" % (page_count - 1, self._pageNumber - 1))
        else:
            # cover page, don't print footer
            pass


def getArabicStyle():
    stylesheet = StyleSheet1()

    stylesheet.add(ParagraphStyle(name='Normal',
                                  fontName='Arabic',
                                  wordWrap='RTL',
                                  alignment=TA_RIGHT,
                                  fontSize=10,
                                  leading=12,
                                  firstLineIndent=0,
                                  rightIndent=0)
                   )

    stylesheet.add(ParagraphStyle(name='TableCell',
                                  fontName='Arabic',
                                  wordWrap='RTL',
                                  alignment=TA_RIGHT,
                                  fontSize=TABLE_FONT_SIZE,
                                  leading=12,
                                  firstLineIndent=0,
                                  rightIndent=0)
                   )

    stylesheet.add(ParagraphStyle(name='TableCellHeader',
                                  fontName='Arabic',
                                  wordWrap='RTL',
                                  alignment=TA_CENTER,
                                  fontSize=TABLE_FONT_SIZE,
                                  leading=12,
                                  firstLineIndent=0,
                                  rightIndent=0)
                   )

    stylesheet.add(ParagraphStyle(name='NameRangeTableCell',
                                  fontName='Arabic-Bold',
                                  wordWrap='RTL',
                                  alignment=TA_RIGHT,
                                  fontSize=20,
                                  leading=20,
                                  firstLineIndent=0,
                                  rightIndent=0)
                   )

    stylesheet.add(ParagraphStyle(name='BlankPageNotice',
                                  fontName='Arabic',
                                  wordWrap='RTL',
                                  alignment=TA_CENTER,
                                  spaceBefore=300,
                                  fontSize=16,
                                  leading=12,
                                  firstLineIndent=0,
                                  rightIndent=0)
                   )

    stylesheet.add(ParagraphStyle(name='Title',
                                  parent=stylesheet['Normal'],
                                  alignment=TA_CENTER,
                                  fontSize=26,
                                  leading=34,
                                  rightIndent=43,
                                  leftIndent=43)
                   )

    stylesheet.add(ParagraphStyle(name='TitleCopyInfo',
                                  parent=stylesheet['Title'],
                                  alignment=TA_CENTER,
                                  fontSize=18,
                                  leading=34,
                                  rightIndent=43,
                                  leftIndent=43)
                   )

    stylesheet.add(ParagraphStyle(name='CoverInfo',
                                  parent=stylesheet['Normal'],
                                  fontSize=16,
                                  leading=36,
                                  rightIndent=75)
                   )
    stylesheet.add(ParagraphStyle(name='CoverInfo-Bold',
                                  parent=stylesheet['CoverInfo'],
                                  fontName='Arabic-Bold')
                   )

    stylesheet.add(ParagraphStyle(name='CenterInfo',
                                  parent=stylesheet['Normal'],
                                  fontSize=13,
                                  leading=18,
                                  spaceBefore=0,
                                  rightIndent=15)
                   )
    stylesheet.add(ParagraphStyle(name='CenterInfo-Bold',
                                  parent=stylesheet['CenterInfo'],
                                  fontName='Arabic-Bold')
                   )

    stylesheet.add(ParagraphStyle(name="CoverStationNumber",
                                  parent=stylesheet['Normal'],
                                  fontSize=40,
                                  fontName='Arabic-Bold',
                                  rightIndent=75)
                   )

    stylesheet.add(ParagraphStyle(name="CoverNameRange",
                                  parent=stylesheet['Normal'],
                                  fontSize=20,
                                  leading=20,
                                  fontName='Arabic-Bold',
                                  rightIndent=75)
                   )

    stylesheet.add(ParagraphStyle(name='StationNumber',
                                  parent=stylesheet['CenterInfo-Bold'],
                                  alignment=TA_LEFT,
                                  leftIndent=10)
                   )

    stylesheet.add(ParagraphStyle(name="SignStationNumber",
                                  parent=stylesheet['CoverStationNumber'],
                                  alignment=TA_CENTER,
                                  rightIndent=0)
                   )

    stylesheet.add(ParagraphStyle(name="SignNameRange",
                                  parent=stylesheet['CoverNameRange'],
                                  rightIndent=140)
                   )

    stylesheet.add(ParagraphStyle(name='PageBottom',
                                  parent=stylesheet['Normal'],
                                  alignment=TA_CENTER,
                                  fontSize=12,
                                  spaceBefore=20)
                   )
    stylesheet.add(ParagraphStyle(name='InnerPageHeader',
                                  fontName='Arabic-Bold',
                                  wordWrap='RTL',
                                  alignment=TA_CENTER,
                                  fontSize=12,
                                  textColor=colors.white,
                                  leading=16,
                                  )
                   )

    return stylesheet


def getHeaderStyle():
    # put page header in a table, so we can set valign
    return TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.darkgrey),
                       ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                       ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                       ('LEADING', (0, 0), (-1, -1), 0),
                       ])


def getTableStyle():
    ts = TableStyle([('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                     ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                     ('LINEBELOW', (0, 0), (-1, -1), 0.8, colors.black),
                     ('BOX', (0, 0), (-1, -1), 0.75, colors.black),
                     ('BOX', (0, 0), (0, -1), 0.75, colors.black),
                     ('BOX', (1, 0), (1, -1), 0.75, colors.black),
                     ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                     ('FONTNAME', (0, 0), (-1, -1), 'Arabic'),
                     ('FONTSIZE', (0, 0), (-1, -1), TABLE_FONT_SIZE),
                     ])
    ts.add('BACKGROUND', (0, 0), (-1, 1), colors.lightgrey)  # header lightgrey
    ts.add('BACKGROUND', (0, 1), (-1, -1), colors.white)  # rest of table
    return ts


def getTableStyleThreeCol():
    ts = TableStyle([('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                     ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                     ('LINEBELOW', (0, 0), (-1, -1), 0.8, colors.black),
                     ('BOX', (0, 0), (-1, -1), 0.75, colors.black),
                     ('BOX', (0, 0), (0, -1), 0.75, colors.black),
                     ('BOX', (1, 0), (1, -1), 0.75, colors.black),
                     ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # center number column
                     ('ALIGN', (1, 0), (1, -1), 'RIGHT'),   # right align name column
                     ('ALIGN', (2, 0), (2, -1), 'CENTER'),  # center number column
                     ('FONTNAME', (0, 0), (-1, -1), 'Arabic'),
                     ('FONTSIZE', (0, 0), (-1, -1), TABLE_FONT_SIZE),
                     ])
    ts.add('BACKGROUND', (0, 0), (-1, 1), colors.lightgrey)  # header lightgrey
    ts.add('BACKGROUND', (0, 1), (-1, -1), colors.white)  # rest of table
    return ts


def hnec_logo(greyscale=False):
    filename = "hnec_logo_grey.png" if greyscale else "hnec_logo.png"
    return open(os.path.join(ASSETS_PATH, filename), 'r')


def cda_logo():
    return open(os.path.join(ASSETS_PATH, "cda_logo.png"), 'r')


def drawHnecLogo(canvas, doc):
    # draws the greyscale hnec logo
    # on the canvas directly, so we don't have to deal with flowables
    canvas.saveState()
    canvas.drawImage(ImageReader(hnec_logo(greyscale=True)), 3.5*cm, A4[1]-3.8*cm, width=4*cm,
                     height=1*cm)
    canvas.restoreState()
