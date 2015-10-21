# -*- coding: utf-8 -*-
# Python imports
from __future__ import unicode_literals

# Django imports
from django.test import TestCase

# Project imports
from .factories import generate_arabic_place_name
from .utils_for_tests import swap_diacritics


class TestTests(TestCase):
    """Tests the test code itself, at least that portion which is complex enough to warrant
    testing (and is relatively easy to test).
    """
    def test_swap_diacritics(self):
        """exercises utils_for_tests.swap_diacritics()"""
        self.assertEqual(swap_diacritics(''), '')
        self.assertEqual(swap_diacritics('abcdefg'), 'abcdefg')
        self.assertEqual(swap_diacritics('ab\u0650cdefg'), 'a\u0650bcdefg')
        self.assertEqual(swap_diacritics('abcdefg\u0650'), 'abcdef\u0650g')
        self.assertEqual(swap_diacritics('ab\u0650cdefg\u0650'), 'a\u0650bcdef\u0650g')
        self.assertEqual(swap_diacritics('ab\u0651cdefg'), 'a\u0651bcdefg')
        self.assertEqual(swap_diacritics('ab\u064ecdefg'), 'a\u064ebcdefg')
        self.assertEqual(swap_diacritics('ab\u064fcdefg'), 'a\u064fbcdefg')
        # Test "unexpected" data (diacritics in position 0)
        self.assertEqual(swap_diacritics('\u0650abcdefg'), '\u0650abcdefg')
        self.assertEqual(swap_diacritics('\u0651abcdefg'), '\u0651abcdefg')
        self.assertEqual(swap_diacritics('\u0651'), '\u0651')

    def test_generate_arabic_place_name(self):
        """exercise generate_arabic_place_name()"""
        self.assertTrue(len(generate_arabic_place_name()) > 1)
        self.assertTrue(len(generate_arabic_place_name(10)) >= 10)
        self.assertTrue(len(generate_arabic_place_name(100)) >= 100)
        self.assertTrue(len(generate_arabic_place_name(1000)) >= 1000)
