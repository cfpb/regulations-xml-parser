# -*- coding: utf-8 -*-

from unittest import TestCase

import lxml.etree as etree
from collections import OrderedDict
from regulation.tree import build_terms_layer, build_reg_tree

import sys
import logging
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

class ParserTests(TestCase):

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
                                                    (u'text', u'Note:\n                  This is a test callout.')])]), 
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


    def test_appendix_intro_references(self):
        reg_xml = etree.fromstring("""
        <appendixSection appendixSecNum="1" label="1024-B-s1" xmlns="eregs">
          <subject/>
          <paragraph label="1024-B-p1-0" marker="">
            <content>The following illustrations provide additional guidance on the meaning and coverage of the provisions of <ref target="1024-2-b-RESPA" reftype="term">RESPA</ref>. Other provisions of Federal or state law may also be applicable to the practices and payments discussed in the following illustrations.</content>
          </paragraph>
        </appendixSection>""")
        result = build_terms_layer(reg_xml)

        # This paragraph is an intro paragraph, so for reg-site the content gets pushed into the appendixSection's text area
        # Therefore, the terms layer should have the reference for the appendixSection's label, not the paragraph's label
        expected_result = OrderedDict([('1024-B-s1', []), (u'referenced', OrderedDict())])

        self.assertEqual(expected_result, result)


    def test_section_intro_references(self):
        reg_xml = etree.fromstring("""
        <section label="1024-3" sectionNum="3" xmlns="eregs">
            <subject>§ 1024.3 Questions or suggestions from public and copies of public guidance documents.</subject>
            <paragraph label="1024-3-p1" marker="">
              <content>Any questions or suggestions from the public regarding <ref target="1024-2-b-RESPA" reftype="term">RESPA</ref>, or requests for copies of <ref target="1024-2-b-PublicGuidanceDocuments" reftype="term">Public Guidance Documents</ref>, should be directed to the Associate Director, Research, Markets, and Regulations, Bureau of Consumer Financial Protection, 1700 G Street NW., Washington, DC 20006. Legal questions concerning the interpretation of this part may be directed to the same address.</content>
            </paragraph>
          </section>""")
        result = build_terms_layer(reg_xml)

        # This paragraph is an intro paragraph, so for reg-site the content gets pushed into the section's text area
        # Therefore, the terms layer should have the reference for the section's label, not the paragraph's label
        expected_result = OrderedDict([('1024-3', []), (u'referenced', OrderedDict())])

        self.assertEqual(expected_result, result)

