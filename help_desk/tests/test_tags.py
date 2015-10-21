from django.http import QueryDict
from django.test import TestCase

from mock import MagicMock

from help_desk.templatetags.help_desk_tags import build_page_link


class TestHelpDeskTags(TestCase):
    def test_build_page_link(self):
        # build_page_link updates the page parm without breaking other parms
        request = MagicMock(
            GET=QueryDict(u'parm1=1&parm1=b&parm2=2&page=18&parm3=3')
        )
        result = build_page_link(request, 13)
        # Old page parm is gone
        self.assertNotIn('page=18', result)
        # New page parm is present
        self.assertIn('page=13', result)
        # Both values of 'parm1' still present
        self.assertIn('parm1=1', result)
        self.assertIn('parm1=b', result)

    def test_build_page_link_no_page_before(self):
        # Similar test, but no page parm in the original parms
        request = MagicMock(
            GET=QueryDict(u'parm1=1&parm1=b&parm2=2&parm3=3')
        )
        result = build_page_link(request, 13)
        # New page parm is present
        self.assertIn('page=13', result)
        # Both values of 'parm1' still present
        self.assertIn('parm1=1', result)
        self.assertIn('parm1=b', result)
