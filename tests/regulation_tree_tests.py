# -*- coding: utf-8 -*-
from __future__ import print_function

from unittest import TestCase
from collections import OrderedDict

import lxml.etree as etree

from common import test_xml
from regulation.tree import (build_reg_tree,
                             build_paragraph_marker_layer,
                             build_terms_layer,
                             build_interp_layer,
                             build_analysis,
                             build_notice,
                             build_formatting_layer,
                             apply_formatting,
                             build_toc_layer,
                             build_keyterm_layer, 
                             get_offset,
                             is_intro_text)
from regulation.node import RegNode


class TreeTestCase(TestCase):

    def setUp(self):
        # A basic test regulation tree (add stuff as necessary for
        # testing)
        self.input_xml = test_xml
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

    def test_build_interp_layer(self):
        interp_dict = build_interp_layer(self.root)
        expected_result = {
                '1234': [{u'reference': '1234-Interp'}],
                '1234-1': [{u'reference': '1234-1-Interp'}],
                '1234-1-A': [{u'reference': '1234-1-A-Interp'}],
        }
        self.assertEqual(expected_result, interp_dict)

    def test_build_analysis(self):
        result_analysis = {
            '1234-1': [{
                'publication_date': u'2015-11-17',
                'reference': (u'2015-12345', u'1234-1')
            }, {
                'publication_date': u'2014-11-17',
                'reference': (u'2014-12345', u'1234-1')
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
                        'I am a paragraph with italicized text.',
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

        self.assertEqual(len(result), 4)
        self.assertEqual(result[0].string_label, '1234-1')
        self.assertEqual(result[0].text, "I'm an unmarked paragraph")
        self.assertEqual(result[0].marker, None)
        self.assertEqual(result[1].string_label, '1234-1-a')
        self.assertEqual(result[1].text, "a I'm a marked paragraph")
        self.assertEqual(result[1].marker, "a")

    def test_flatten_tree(self):

        xml_tree = etree.fromstring(test_xml)
        reg_tree = build_reg_tree(xml_tree)

        result = reg_tree.flatten()

        self.assertEqual(1, 1)

    def test_labels(self):

        xml_tree = etree.fromstring(test_xml)
        reg_tree = build_reg_tree(xml_tree)

        result = reg_tree.labels()

        self.assertEqual(1, 1)

    def test_height(self):
        xml_tree = etree.fromstring(test_xml)
        reg_tree = build_reg_tree(xml_tree)

        result = reg_tree.height()

        self.assertEqual(result, 5)

    def test_markerless_nodes(self):
        """ Make sure marker: '' comes through in the json """
        xml_tree = etree.fromstring(test_xml)
        reg_tree = build_reg_tree(xml_tree)

        parent = reg_tree.find_node(lambda n: n.string_label == '1234-1-a')[0]
        self.assertEqual(parent.children[0].to_json()['marker'], '')
        self.assertEqual(parent.children[1].to_json()['marker'], '')

    def test_build_formatting_layer_variable(self):
        tree = etree.fromstring("""
        <section xmlns="eregs">
          <paragraph label="foo">
            <content>
              <variable>Val<subscript>n</subscript></variable>
            </content>
          </paragraph>
        </section>
        """)
        expected_result = {
            'foo': [{
                'locations': [0],
                'subscript_data': {
                    'subscript': 'n',
                    'variable': 'Val'
                },
                'text': 'Val_{n}'
            }]
        }
        result = build_formatting_layer(tree)
        self.assertEqual(expected_result, result)

    def test_apply_formatting_variable(self):
        content = etree.fromstring("""
        <content xmlns="eregs">
          The variable <variable>Val<subscript>n</subscript></variable> means something.
        </content>
        """, parser=etree.XMLParser(remove_blank_text=True))
        expected_result = etree.fromstring("""
        <content xmlns="eregs">
          The variable Val_{n} means something.
        </content>
        """,)
        result = apply_formatting(content)
        self.assertEqual(expected_result.text, result.text)

    def test_build_formatting_layer_callout(self):
        tree = etree.fromstring("""
        <section xmlns="eregs">
          <paragraph label="foo">
            <content>
              <callout type="note">
                <line>Note:</line>
                <line>Some notes</line>
              </callout>
            </content>
          </paragraph>
        </section>
        """, parser=etree.XMLParser(remove_blank_text=True))
        expected_result = {
            'foo': [{
                'fence_data': {
                    'lines': [
                        'Note:',
                        'Some notes'
                    ],
                    'type': 'note'
                },
                'locations': [
                    0
                ],
                'text': 'Note:Some notes',
            }]
        }
        result = build_formatting_layer(tree)
        self.assertEqual(expected_result, result)

    def test_apply_formatting_callout_note(self):
        content = etree.fromstring("""
        <content xmlns="eregs">
          <callout type="note">
            <line>Note:</line>
            <line>Some notes</line>
          </callout>
        </content>
        """, parser=etree.XMLParser(remove_blank_text=True))
        expected_result = etree.fromstring("""
        <content xmlns="eregs">
          Note:Some notes
        </content>
        """, parser=etree.XMLParser(remove_blank_text=True))
        result = apply_formatting(content)
        self.assertEqual(expected_result.text.strip(), result.text)

    def test_build_formatting_layer_dash(self):
        tree = etree.fromstring("""
        <section xmlns="eregs">
          <paragraph label="foo">
            <content>
              <dash>Date</dash>
            </content>
          </paragraph>
        </section>
        """, parser=etree.XMLParser(remove_blank_text=True))
        expected_result = {
            'foo': [{
                'dash_data': {
                    'text': 'Date'
                }, 
                'locations': [
                    0
                ], 
                'text': 'Date_____',
            }]
        }
        result = build_formatting_layer(tree)
        self.assertEqual(expected_result, result)

    def test_apply_formatting_dash(self):
        content = etree.fromstring("""
        <content xmlns="eregs">
          <dash>Date</dash>
        </content>
        """, parser=etree.XMLParser(remove_blank_text=True))
        expected_result = etree.fromstring("""
        <content xmlns="eregs">
          Date_____
        </content>
        """, parser=etree.XMLParser(remove_blank_text=True))
        result = apply_formatting(content)
        self.assertEqual(expected_result.text.strip(), result.text)

    def test_build_reg_tree_intro_para(self):
        tree = etree.fromstring("""
        <section label="foo" xmlns="eregs">
          <subject>Some Subject</subject>
          <paragraph label="foo-p1" marker="">
            <content>
              An unmarked intro paragraph.
            </content>
          </paragraph>
          <paragraph label="foo-a" marker="a">
            <content>A marked paragraph</content>
          </paragraph>
        </section>
        """)
        expected_result = {
            'children': [
                {
                    'children': [],
                    'label': [
                        'foo',
                        'a'
                    ],
                    'node_type': 'regtext',
                    'text': 'a A marked paragraph',
                    'marker': 'a'
                }
            ],
            'label': [
                'foo'
            ],
            'node_type': 'regtext',
            'text': 'An unmarked intro paragraph.',
            'title': 'Some Subject'
        }
        result = build_reg_tree(tree)
        self.assertEqual(expected_result, result.to_json())

    def test_appendix_callout(self):
        reg_xml = etree.fromstring("""
        <appendixSection appendixSecNum="6" label="1024-A-h6" xmlns="eregs">
          <subject>Instructions for Completing HUD-1A</subject>
          <paragraph label="1024-A-h6-p92" marker="">
            <content>
              <callout type="note">
                <line>Note:</line>
                <line>The HUD-1A is an optional form that may be used for refinancing and subordinate-lien federally related mortgage loans, as well as for any other one-party transaction that does not involve the transfer of title to residential real property. The HUD-1 form may also be used for such transactions, by utilizing the borrower's side of the HUD-1 and following the relevant parts of the instructions as set forth above. The use of either the HUD-1 or HUD-1A is not mandatory for open-end lines of credit (home-equity plans), as long as the provisions of Regulation Z are followed.</line>
              </callout>
            </content>
          </paragraph>
        </appendixSection>""")
        result = build_reg_tree(reg_xml)

        expected_result = {
            "children": [
                {
                    "children": [],
                    "label": [
                        "1024",
                        "A",
                        "h6",
                        "p92"
                    ],
                    "marker": "",
                    "node_type": "appendix",
                    "text": "Note:\n                The HUD-1A is an optional form that may be used for refinancing and subordinate-lien federally related mortgage loans, as well as for any other one-party transaction that does not involve the transfer of title to residential real property. The HUD-1 form may also be used for such transactions, by utilizing the borrower's side of the HUD-1 and following the relevant parts of the instructions as set forth above. The use of either the HUD-1 or HUD-1A is not mandatory for open-end lines of credit (home-equity plans), as long as the provisions of Regulation Z are followed."
                }
            ],
            "label": [
                "1024",
                "A",
                "h6"
            ],
            "node_type": "appendix",
            "text": "",
            "title": "Instructions for Completing HUD-1A"
        }

        # This callout should correctly get identified as NOT an intro paragraph, and its content should stay in
        # an element with the paragraph's label and not smushed into the appendixSection's label
        self.assertEqual(expected_result, result.to_json())

    def test_section_callout(self):
        reg_xml = etree.fromstring("""
          <section label="1024-3" sectionNum="3" xmlns="eregs">
            <subject>§ 1024.3 Questions or suggestions from public and copies of public guidance documents.</subject>
            <paragraph label="1024-3-p1" marker="">
              <content>
                <callout type="note">
                  <line>Note:</line>
                  <line>This is a test callout.</line>
                </callout>
              </content>
            </paragraph>
          </section>""")
        result = build_reg_tree(reg_xml)

        expected_result = OrderedDict([(u'children',
                                      [OrderedDict([(u'children', []),
                                                    (u'label', [u'1024', u'3', u'p1']),
                                                    (u'node_type', u'regtext'),
                                                    (u'text', u'Note:\n                  This is a test callout.'),
                                                    (u'marker', u''),
                                                    ])]),
                                       (u'label',
                                        [u'1024', u'3']),
                                       (u'node_type', u'regtext'),
                                       (u'text', u''),
                                       (u'title', u'\xa7 1024.3 Questions or suggestions from public and copies of public guidance documents.')
                                      ]
                                     )


        # This callout should correctly get identified as NOT an intro paragraph, and its content should stay in
        # an element with the paragraph's label and not smushed into the section's label
        self.assertEqual(expected_result, result.to_json())

    def test_appendix_graphic(self):
        reg_xml = etree.fromstring("""
          <appendixSection appendixSecNum="1" label="1013-A-1" xmlns="eregs">
              <subject>A-1—Model Open-End or Finance Vehicle Lease Disclosures</subject>
              <paragraph label="1013-A-1-p1" marker="">
                <content>
                  <graphic>
                    <altText></altText>
                    <text>![](ER19DE11.010)</text>
                    <url>https://s3.amazonaws.com/images.federalregister.gov/ER19DE11.010/original.gif</url>
                  </graphic>
                </content>
              </paragraph>
          </appendixSection>""")
        result = build_reg_tree(reg_xml)

        expected_result = OrderedDict([(u'children',
                              [OrderedDict([(u'children', []),
                                          (u'label', [u'1013', u'A', u'1', u'p1']),
                                          (u'node_type', u'appendix'),
                                          (u'text', '![](ER19DE11.010)'),
                                          (u'marker', ''),
                                  ])]),
                                  (u'label', [u'1013', u'A', u'1']), (u'node_type', u'appendix'),
                                  (u'text', u''),
                                  (u'title', u'A-1\u2014Model Open-End or Finance Vehicle Lease Disclosures')])

        # This graphic should correctly get identified as NOT an intro paragraph, and its content should stay in
        # an element with the paragraph's label and not smushed into the section's label
        self.assertEqual(expected_result, result.to_json())

    def test_appendix_intro_references(self):
        reg_xml = etree.fromstring("""
        <appendixSection appendixSecNum="1" label="1024-B-s1" xmlns="eregs">
          <subject/>
          <paragraph label="1024-B-p1-0" marker="">
            <content>The following illustrations provide provisions of <ref target="1024-defs" reftype="term">RESPA</ref>.
            </content>
          </paragraph>
          <paragraph label="1024-B-p1-1" marker="">
            <content>Refer to the <ref target="1024-defs" reftype="term">Bureau</ref>'s regulations for <ref target="1024-defs" reftype="term">HUD-1</ref>.
            </content>
          </paragraph>
          <paragraph label="1024-defs" marker="">
            <content>This paragraph contains terms <def term="bureau">Bureau</def>, <def term="respa">RESPA</def>, and <def term="hud-1">HUD-1</def>.
            </content>
          </paragraph>
        </appendixSection>""")
        result = build_terms_layer(reg_xml)

        # This paragraph is an intro paragraph, so for reg-site the content gets pushed into the appendixSection text
        # Therefore, the terms layer should have the reference for the appendixSection's label, not the paragraph label
        # This also checks that only the first paragraph becomes an intro paragraph.
        expected_result = OrderedDict([('1024-B-s1', 
                                [OrderedDict([(u'offsets', [[50, 55]]), 
                                              (u'ref', u'bureau:1024-defs')])]),
                               ('1024-B-p1-1', 
                                [OrderedDict([(u'offsets', [[13, 19]]),
                                              (u'ref', u'bureau:1024-defs')]), 
                                 OrderedDict([(u'offsets', [[38, 43]]),
                                              (u'ref', u'bureau:1024-defs')])]),
                               (u'referenced', OrderedDict([
                                                    (u'bureau:1024-defs', 
                                                     OrderedDict([(u'position', [30, 36]),
                                                                  (u'reference', '1024-defs'),
                                                                  (u'term', 'bureau')])),
                                                    (u'respa:1024-defs', 
                                                     OrderedDict([(u'position', [38, 43]),
                                                                  (u'reference', '1024-defs'),
                                                                  (u'term', 'respa')])),
                                                    (u'hud-1:1024-defs',
                                                     OrderedDict([(u'position', [49, 54]),
                                                                  (u'reference', '1024-defs'),
                                                                  (u'term', 'hud-1')]))]))])

        self.assertEqual(expected_result, result)

    def test_section_intro_references(self):
        reg_xml = etree.fromstring("""
        <section label="1024-3" sectionNum="3" xmlns="eregs">
            <subject>§ 1024.3 Questions or suggestions from public and copies of public guidance documents.</subject>
            <paragraph label="1024-3-p1" marker="">
              <content>Any questions regarding <ref target="1024-defs" reftype="term">RESPA</ref>.
              </content>
            </paragraph>
            <paragraph label="1024-defs" marker="">
              <content>This paragraph contains references for the term <def term="respa">RESPA</def>.
              </content>
            </paragraph>
          </section>""")
        result = build_terms_layer(reg_xml)

        # This paragraph is an intro paragraph, so for reg-site the content gets pushed into the section's text area
        # Therefore, the terms layer should have the reference for the section's label, not the paragraph's label
        expected_result = OrderedDict([('1024-3', 
                                        [OrderedDict([(u'offsets', [[24, 29]]),
                                                      (u'ref', u'respa:1024-defs')])]),
                                       (u'referenced', 
                                        OrderedDict([(u'respa:1024-defs', 
                                        OrderedDict([(u'position', [48, 53]),
                                                     (u'reference', '1024-defs'),
                                                     (u'term', 'respa')]))]))])

        self.assertEqual(expected_result, result)

    def test_build_toc_layer_part(self):
        tree = etree.fromstring("""
        <part xmlns="eregs" label="1234">
          <tableOfContents>
            <tocSecEntry target="1234-1">
              <sectionNum>1</sectionNum>
              <sectionSubject>§ 1234.1</sectionSubject>
            </tocSecEntry>
            <tocAppEntry target="1234-A">
              <appendixLetter>A</appendixLetter>
              <appendixSubject>Appendix</appendixSubject>
            </tocAppEntry>
          </tableOfContents>
          <content/>
        </part>
        """)
        expected_result = {
            '1234': [
                {'index': [u'1234', u'1'], 'title': u'\xa7 1234.1'},
                {'index': [u'1234', u'A'], 'title': 'Appendix'}
            ],
        }
        result = build_toc_layer(tree)
        self.assertEqual(expected_result, result)
        
    def test_build_toc_layer_subpart(self):
        tree = etree.fromstring("""
        <subpart xmlns="eregs" subpartLetter="A" label="1234-Subpart-A">
          <title>General</title>
          <tableOfContents label="1234-Subpart-A-TOC">
            <tocSecEntry target="1234-1">
              <sectionNum>1</sectionNum>
              <sectionSubject>§ 1234.1</sectionSubject>
            </tocSecEntry>
            <tocSecEntry target="1234-1">
              <sectionNum>1</sectionNum>
              <sectionSubject>§ 1234.2</sectionSubject>
            </tocSecEntry>
          </tableOfContents>
          <content></content>
        </subpart>
        """)
        expected_result = {
            '1234-Subpart-A': [
                {'index': [u'1234', u'1'], 'title': u'\xa7 1234.1'},
                {'index': [u'1234', u'1'], 'title': u'\xa7 1234.2'}
            ],
        }
        result = build_toc_layer(tree)
        self.assertEqual(expected_result, result)
        
    def test_build_toc_layer_section(self):
        tree = etree.fromstring("""
        <section xmlns="eregs" label="1234-1" sectionNum="1">
          <subject>§ 1234.1</subject>
          <tableOfContents label="1234-Subpart-A-TOC">
            <tocSecEntry target="1234-1-a">
              <sectionNum>1</sectionNum>
              <sectionSubject>§ 1234.1(a)</sectionSubject>
            </tocSecEntry>
          </tableOfContents>
          <paragraph label="1234-1-a" marker="a">
            <content>This is a section with its own TOC</content>
          </paragraph>
        </section>
        """)
        expected_result = {
            '1234-1': [
                {u'index': [u'1234', u'1', u'a'], u'title': u'\xa7 1234.1(a)'}
            ],
        }
        result = build_toc_layer(tree)
        self.assertEqual(expected_result, result)

    def test_build_toc_layer_appendix(self):
        tree = etree.fromstring("""
        <appendix xmlns="eregs" appendixLetter="A" label="1234-A">
          <appendixTitle>Appendix A</appendixTitle>
          <tableOfContents>
            <tocAppEntry target="1234-A-1">
              <appendixLetter>A-1</appendixLetter>
              <appendixSubject>Some Subject</appendixSubject>
            </tocAppEntry>
          </tableOfContents>
        </appendix>
        """)
        expected_result = {
            '1234-A': [
                {u'index': [u'1234', u'A', u'1'], u'title': 'Some Subject'}
            ],
        }
        result = build_toc_layer(tree)
        self.assertEqual(expected_result, result)
        
    def test_build_toc_layer_appendix_section(self):
        tree = etree.fromstring("""
        <appendix xmlns="eregs" appendixLetter="A" label="1234-A">
          <appendixTitle>Appendix A</appendixTitle>
          <appendixSection appendixSecNum="1" label="1234-A-1">
            <subject>Section 1</subject>
            <tableOfContents>
              <tocAppEntry target="1234-A-1-A">
                <appendixLetter>A-1-A</appendixLetter>
                <appendixSubject>Something</appendixSubject>
              </tocAppEntry>
            </tableOfContents>
            <paragraph label="1234-A-1-A" marker="">
              <content>Something here</content>
            </paragraph>
          </appendixSection>
        </appendix>
        """)
        expected_result = {
            '1234-A-1': [
                {u'index': [u'1234', u'A', u'1', 'A'], u'title': 'Something'}
            ],
        }
        result = build_toc_layer(tree)
        self.assertEqual(expected_result, result)

    def test_para_with_defs_offsets(self):
        reg_xml = etree.fromstring("""
        <appendixSection appendixSecNum="1" label="1024-s1" xmlns="eregs">
          <subject/>
          <paragraph label="1024-defs" marker="1.">
            <title type="keyterm">Definitions.</title>
            <content>This paragraph contains definitions to check offsets, like <def term="bureau">Bureau</def>.
            </content>
          </paragraph>
        </appendixSection>""")
        result = build_terms_layer(reg_xml)

        # This paragraph is a paragraph with definitions and a title (type: keyterm) to test
        # that the appropriate offsets are calculated for both marker and title.
        expected_result = OrderedDict([(u'referenced', 
                                        OrderedDict([(u'bureau:1024-defs',
                                                      OrderedDict([(u'position', [74, 80]),
                                                                   (u'reference', '1024-defs'),
                                                                   (u'term', 'bureau')]))])
                                        )])

        self.assertEqual(expected_result, result)

    def test_build_keyterm_layer_subpart(self):
        """ Make sure subpart paragraphs with keyterms are properly
            recognized """
        tree = etree.fromstring("""
        <section label="1234-1" xmlns="eregs">
          <paragraph label="1234-1-a" marker="a">
           <title type="keyterm">Keyterm.</title>
            <content>I'm a paragraph</content>
          </paragraph>
        </section>
        """)
        expected_result = {
            '1234-1-a': [
                {'locations': [0], 
                 'key_term': 'Keyterm.'}
            ],
        }
        result = build_keyterm_layer(tree)
        self.assertEqual(expected_result, dict(result))

    def test_build_keyterm_layer_appendix(self):
        """ Make sure appendix paragraphs with keyterms are properly
            recognized """
        tree = etree.fromstring("""
        <appendixSection appendixSecNum="1" label="1234-A-p1" xmlns="eregs">
          <subject/>
            <paragraph label="1234-A-1" marker="1">
              <title type="keyterm">Keyterm.</title>
              <content>I'm a paragraph</content>
            </paragraph>
        </appendixSection>
        """)
        expected_result = {
            '1234-A-1': [
                {'locations': [0], 
                 'key_term': 'Keyterm.'}
            ],
        }
        result = build_keyterm_layer(tree)
        self.assertEqual(expected_result, result)

    def test_build_keyterm_layer_interp(self):
        """ Make sure interpParagraphs with keyterms are properly
            recognized """
        tree = etree.fromstring("""
        <interpSection label="1234-1-Interp" target="1234-1" xmlns="eregs">
          <interpParagraph label="1234-1-A-Interp" target="1234-1-A">
            <title type="keyterm">Keyterm.</title>
            <content>Some interpretation content here.</content>
          </interpParagraph>
        </interpSection>
        """)
        expected_result = {
            '1234-1-A-Interp': [
                {'locations': [0], 
                 'key_term': 'Keyterm.'}
            ],
        }
        result = build_keyterm_layer(tree)
        self.assertEqual(expected_result, result)

    def test_get_offset(self):
        """ Make sure offsets returned are correct """
        element = etree.fromstring("""
          <paragraph xmlns="eregs" marker="(1)">
            <title type="keyterm">Keyterm.</title>
            <content>Some content here.</content>
          </paragraph>
        """)
        marker = "(1)"
        title = etree.fromstring("""
          <title type="keyterm">Keyterm.</title>
        """)
        result = get_offset(element, marker, title)
        self.assertEqual(12, result)

        element = etree.fromstring("""
          <interpParagraph xmlns="eregs" marker="(1)">
            <title type="keyterm">Keyterm.</title>
            <content>Some content here.</content>
          </interpParagraph>
        """)
        marker = "(1)"
        title = etree.fromstring("""
          <title type="keyterm">Keyterm.</title>
        """)
        result = get_offset(element, marker, title)
        self.assertEqual(8, result)
        
    def test_is_intro_text(self):
        # Has a title
        with_title = etree.fromstring("""
        <paragraph xmlns="eregs" marker="">
            <title>A Title</title>
            <content>Some content.</content>
        </paragraph>""")
        self.assertFalse(is_intro_text(with_title))

        # Has a marker
        with_marker = etree.fromstring("""
        <paragraph xmlns="eregs" marker="1.">
            <content>Some content.</content>
        </paragraph>""")
        self.assertFalse(is_intro_text(with_marker))

        # Wrong index in parent
        wrong_index = etree.fromstring("""
        <paragraph xmlns="eregs" marker="1.">
            <content>Some content.</content>
        </paragraph>""")
        parent = etree.Element('parent')
        parent.append(etree.Element('{eregs}paragraph'))
        parent.append(wrong_index)
        self.assertFalse(is_intro_text(wrong_index))

        # Wrong index in parent
        no_callouts = etree.fromstring("""
        <paragraph xmlns="eregs" marker="1.">
            <content><callout><line>A line.</line></callout></content>
        </paragraph>""")
        etree.Element('parent').append(no_callouts)
        self.assertFalse(is_intro_text(no_callouts))

        # Has some child paragraphs
        has_children = etree.fromstring("""
        <paragraph xmlns="eregs" marker="">
            <content>Some content.</content>
            <paragraph marker="1.">
                <content>Child paragraph 1.</content>
            </paragraph>
            <paragraph marker="2.">
                <content>Child paragraph 2.</content>
            </paragraph>
        </paragraph>""")
        etree.Element('parent').append(has_children)
        self.assertFalse(is_intro_text(has_children))

        # Perfect
        intro_text = etree.fromstring("""
        <paragraph xmlns="eregs" marker="">
            <content>Some content.</content>
        </paragraph>""")
        etree.Element('parent').append(intro_text)
        self.assertTrue(is_intro_text(intro_text))
