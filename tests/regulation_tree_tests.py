# -*- coding: utf-8 -*-

from unittest import TestCase

import lxml.etree as etree

from regulation.tree import build_analysis, build_notice


class TreeTestCase(TestCase):

    def setUp(self):
        # A basic test regulation tree
        self.input_xml = """
        <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
          <fdsys>
            <date>2015-11-17</date>
          </fdsys>
          <preamble>
            <documentNumber>2015-12345</documentNumber>
          </preamble>
          <part partNumber="1234">
            <content>
              <subpart>
                <content>
                  <section label="1234-1">
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
            </content>
          </part>
        </regulation>
        """  # NOQA
        self.root = etree.fromstring(self.input_xml)

    def tearDown(self):
        pass

    def test_build_analysis(self):
        result_analysis = {
            '1234-1': [{
                'publication_date': u'2015-11-17', 
                'reference': (u'2015-12345', u'1234-1')
            }]
        }
        analysis_dict = build_analysis(self.root)
        self.assertEqual(result_analysis, dict(analysis_dict))

    def test_build_notice(self):
        result_notice = {
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
