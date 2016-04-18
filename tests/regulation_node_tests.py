# -*- coding: utf-8 -*-
from __future__ import print_function

from unittest import TestCase

import lxml.etree as etree

from regulation.node import find_all_occurrences

import settings

class NodeTests(TestCase):

    def test_find_all_occurrences(self):
        s = "There are many days. Sunday is a day. Saturday is a day too. Days happen.".lower()
        occurances = find_all_occurrences(s, 'day')
        self.assertTrue(33 in occurances)
        self.assertTrue(52 in occurances)
        self.assertEqual(len(occurances), 2)
        occurances = find_all_occurrences(s, 'days')
        self.assertTrue(15 in occurances)
        self.assertTrue(61 in occurances)
        self.assertEqual(len(occurances), 2)

