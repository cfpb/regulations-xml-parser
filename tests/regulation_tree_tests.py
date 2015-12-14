# -*- coding: utf-8 -*-

from unittest import TestCase

import lxml.etree as etree

from regulation.tree import (build_reg_tree,
                             build_paragraph_marker_layer,
                             build_analysis,
                             build_notice)


class TreeTestCase(TestCase):

    def setUp(self):
        # A basic test regulation tree (add stuff as necessary for
        # testing)
        self.input_xml = """
        <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
          <fdsys>
            <date>2015-11-17</date>
            <title>REGULATION TESTING</title>
          </fdsys>
          <preamble>
            <cfr>
              <title>12</title>
              <section>1234</section>
            </cfr>
            <documentNumber>2015-12345</documentNumber>
            <effectiveDate>2015-11-17</effectiveDate>
            <federalRegisterURL>https://www.federalregister.gov/some/url/</federalRegisterURL>
          </preamble>
          <part partNumber="1234">
            <content>

              <subpart>
                <content>
                  <section label="1234-1">
                    <subject/>
                    <paragraph label="1234-1-p1" marker="">
                      <content>I'm an unmarked paragraph</content>
                    </paragraph>
                    <paragraph label="1234-1-a" marker="a">
                      <content>I'm a marked paragraph</content>
                    </paragraph>
                    <analysis>
                      <analysisSection>
                        <title>Section 1234.1</title>
                        <analysisParagraph>This paragraph is in the top-level section.</analysisParagraph>
                        <analysisSection>
                          <title>(a) Section of the Analysis</title>
                          <analysisParagraph>I am a paragraph<footnote ref="1">Paragraphs contain text.</footnote> in an analysis<footnote ref="2">Analysis analyzes things.</footnote> section, love me!</analysisParagraph>
                        </analysisSection>
                      </analysisSection>
                    </analysis>
                  </section>
                </content>
              </subpart>

              <appendix appendixLetter="A" label="1234-A">
                <appendixTitle>Appendix A to Part 1234</appendixTitle>
                <appendixSection appendixSecNum="1" label="1234-A-p1">
                  <subject/>
                  <paragraph label="1234-A-p1-p1" marker="">
                    <content>This is some appendix content.</content>
                  </paragraph>
                </appendixSection>
              </appendix>

              <interpretations label="1234-Interp">
                <title>Supplement I to Part 1234&#8212;Official Interpretations</title>
                <interpSection label="1234-Interp-h1">
                  <title>Introduction</title>
                  <interpParagraph label="1234-Interp-h1-1" target="1013-h1-1">
                    <content>Some interpretation content here.</content>
                  </interpParagraph>
                </interpSection>
              </interpretations>

            </content>
          </part>
        </regulation>
        """  # NOQA
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

        subpart_dict = node_dict['children'][0]
        self.assertEqual(subpart_dict['label'], ['1234', 'Subpart'])

        appendix_dict = node_dict['children'][1]
        self.assertEqual(appendix_dict['label'], ['1234', 'A'])

        interp_dict = node_dict['children'][2]
        self.assertEqual(interp_dict['label'], ['1234', 'Interp'])

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
