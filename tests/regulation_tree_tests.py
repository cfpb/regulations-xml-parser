# -*- coding: utf-8 -*-

from unittest import TestCase

import lxml.etree as etree

from common import test_xml
from regulation.tree import (build_reg_tree,
                             build_paragraph_marker_layer,
                             build_analysis,
                             build_notice)
from regulation.node import RegNode


class TreeTestCase(TestCase):

    def setUp(self):
        # A basic test regulation tree (add stuff as necessary for
        # testing)
        self.input_xml = test_xml  # NOQA
        self.root = etree.fromstring(self.input_xml)

    def tearDown(self):
        pass

    def test_build_reg_tree(self):
        # Do some basic introspection of the outcome
        node = build_reg_tree(self.root)

        node_dict = node.to_json()
        self.assertEqual(node_dict['title'], 'REGULATION TESTING')
        self.assertEqual(node_dict['label'], ['1234'])
        self.assertEqual(len(node_dict['children']), 3)
        self.assertEqual(node.depth, 0)

        subpart_dict = node_dict['children'][0]
        self.assertEqual(subpart_dict['label'], ['1234', 'Subpart'])
        self.assertEqual(node.children[0].depth, 1)

        appendix_dict = node_dict['children'][1]
        self.assertEqual(appendix_dict['label'], ['1234', 'A'])
        self.assertEqual(node.children[1].depth, 1)

        interp_dict = node_dict['children'][2]
        self.assertEqual(interp_dict['label'], ['1234', 'Interp'])
        self.assertEqual(node.children[2].depth, 1)

    def test_build_analysis(self):
        result_analysis = {
            '1234-1': [{
                'publication_date': u'2015-11-17',
                'reference': (u'2015-12345', u'1234-1')
            }]
        }
        analysis_dict = build_analysis(self.root)
        self.assertEqual(result_analysis, dict(analysis_dict))

    def test_build_paragraph_marker_layer(self):
        result = build_paragraph_marker_layer(self.root)
        self.assertEqual(result,
                         {'1234-1-a': [{'locations': [0], 'text': 'a'}]})

    def test_build_notice(self):
        result_notice = {
            'cfr_parts': ['1234'],
            'effective_on': '2015-11-17',
            'publication_date': '2015-11-17',
            'fr_url': 'https://www.federalregister.gov/some/url/',
            'document_number': '2015-12345',
            'section_by_section': [{
                'labels': ['1234-1'],
                'title': 'Section 1234.1',
                'paragraphs': [
                    'This paragraph is in the top-level section.',
                ],
                'footnote_refs': [],
                'children': [{
                    'children': [],
                    'footnote_refs': [
                        {
                            'offset': 16,
                            'paragraph': 0,
                            'reference': '1'
                        },
                        {
                            'offset': 31,
                            'paragraph': 0,
                            'reference': '2'
                        },
                    ],
                    'paragraphs': [
                        'I am a paragraph in an analysis section, love me!',
                    ],
                    'title': '(a) Section of the Analysis'
                }],
            }],
            'footnotes': {
                '1': 'Paragraphs contain text.',
                '2': 'Analysis analyzes things.'
            },
        }

        notice_dict = build_notice(self.root)
        self.assertEqual(result_notice, dict(notice_dict))

    def test_find_node_single(self):

        xml_tree = etree.fromstring(test_xml)
        reg_tree = build_reg_tree(xml_tree)

        def predicate(node):
            if node.string_label == '1234-1-a':
                return True
            else:
                return False

        result = reg_tree.find_node(predicate)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].string_label, '1234-1-a')
        self.assertEqual(result[0].text, "a I'm a marked paragraph")
        self.assertEqual(result[0].marker, "a")
        self.assertEqual(result[0].depth, 3)

    def test_find_node_multiple(self):

        xml_tree = etree.fromstring(test_xml)
        reg_tree = build_reg_tree(xml_tree)

        def predicate(node):
            if node.text.find('marked') > -1:
                return True
            else:
                return False

        result = reg_tree.find_node(predicate)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].string_label, '1234-1-p1')
        self.assertEqual(result[0].text, "I'm an unmarked paragraph")
        self.assertEqual(result[0].marker, "")
        self.assertEqual(result[1].string_label, '1234-1-a')
        self.assertEqual(result[1].text, "a I'm a marked paragraph")
        self.assertEqual(result[1].marker, "a")

    def test_flatten_tree(self):

        xml_tree = etree.fromstring(test_xml)
        reg_tree = build_reg_tree(xml_tree)

        result = reg_tree.flatten()

        print result

        self.assertEqual(1, 1)

    def test_labels(self):

        xml_tree = etree.fromstring(test_xml)
        reg_tree = build_reg_tree(xml_tree)

        result = reg_tree.labels()

        print result

        self.assertEqual(1, 1)

    def test_height(self):

        xml_tree = etree.fromstring(test_xml)
        reg_tree = build_reg_tree(xml_tree)

        result = reg_tree.height()

        self.assertEqual(result, 4)

