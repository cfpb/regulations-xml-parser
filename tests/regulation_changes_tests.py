# -*- coding: utf-8 -*-

from unittest import TestCase

import lxml.etree as etree

from regulation.changes import (get_parent_label, get_sibling_label,
                                process_changes, generate_diff)


class ChangesTests(TestCase):

    def test_get_parent_label_normal(self):
        label_parts = ['1234', '1', 'g', '2']
        self.assertEqual(['1234', '1', 'g'],
                         get_parent_label(label_parts))

    def test_get_parent_label_root(self):
        label_parts = ['1234']
        self.assertEqual(None, get_parent_label(label_parts))

    def test_get_parent_label_interps(self):
        label_parts = ['1234', '1', 'g', '2', 'Interp']
        self.assertEqual(['1234', '1', 'g', 'Interp'],
                         get_parent_label(label_parts))

        label_parts = ['1234', '1', 'g', '2', 'Interp', '2']
        self.assertEqual(['1234', '1', 'g', '2', 'Interp'],
                         get_parent_label(label_parts))

    def test_get_parent_label_part_interp(self):
        label_parts = ['1234', 'Interp']
        self.assertEqual(['1234', ],
                         get_parent_label(label_parts))
        
    def test_get_parent_label_part_subpart(self):
        label_parts = ['1234', 'Subpart', 'A']
        self.assertEqual(['1234', ],
                         get_parent_label(label_parts))
        
    def test_get_sibling_label_alpha(self):
        label_parts = ['1234', '1', 'g']
        self.assertEqual(['1234', '1', 'f'],
                         get_sibling_label(label_parts))

    def test_get_sibling_label_numeric(self):
        label_parts = ['1234', '2']
        self.assertEqual(['1234', '1'],
                         get_sibling_label(label_parts))

    def test_get_sibling_label_interp(self):
        label_parts = ['1234', '1', 'g', '2', 'Interp']
        self.assertEqual(['1234', '1', 'g', '1', 'Interp'],
                         get_sibling_label(label_parts))

    def test_get_sibling_label_part_interp(self):
        label_parts = ['1234', 'Interp']
        self.assertEqual(None, get_sibling_label(label_parts))
        
    def test_get_sibling_label_none(self):
        label_parts = ['1234', '1', 'a']
        self.assertEqual(None, get_sibling_label(label_parts))

    def test_process_changes_meta(self):
        notice_xml = etree.fromstring("""
            <notice xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys>
                This is an fdsys 
              </fdsys>
              <preamble>
                This is the preamble
              </preamble>
            </notice>""")
        original_xml = etree.fromstring("""
            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys>
                Old fdsys
              </fdsys>
              <preamble>
                Old preamble
              </preamble>
            </regulation>""") # noqa
        new_xml = process_changes(original_xml, notice_xml)
        fdsys = new_xml.find('./{eregs}fdsys')
        preamble = new_xml.find('./{eregs}preamble')
        self.assertTrue("This is an fdsys" in fdsys.text)
        self.assertTrue("This is the preamble" in preamble.text)

    def test_process_changes_added(self):
        notice_xml = etree.fromstring("""
            <notice xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys><preamble></preamble>
              <changeset>
                <change operation="added" label="1234-2">
                  <paragraph label="1234-2">An added paragraph</paragraph>
                </change>
              </changeset>
            </notice>""")
        original_xml = etree.fromstring("""
            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys>
              <preamble></preamble>
              <part label="1234">
                <content>
                  <paragraph label="1234-1">An existing paragraph</paragraph>
                </content>
              </part>
            </regulation>""")
        new_xml = process_changes(original_xml, notice_xml)
        new_para = new_xml.find('.//{eregs}paragraph[@label="1234-2"]')
        self.assertNotEqual(new_para, None)
        self.assertEqual("An added paragraph", new_para.text)
        self.assertEqual(new_para.getparent().index(new_para), 1)

    def test_process_changes_added_first_child(self):
        notice_xml = etree.fromstring("""
            <notice xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys><preamble></preamble>
              <changeset>
                <change operation="added" label="1234-1">
                  <paragraph label="1234-1">An added paragraph</paragraph>
                </change>
              </changeset>
            </notice>""")
        original_xml = etree.fromstring("""
            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys>
              <preamble></preamble>
              <part label="1234">
                <content/>
              </part>
            </regulation>""")
        new_xml = process_changes(original_xml, notice_xml)
        new_para = new_xml.find('.//{eregs}paragraph[@label="1234-1"]')
        self.assertNotEqual(new_para, None)
        self.assertEqual("An added paragraph", new_para.text)

    def test_process_changes_added_existing(self):
        notice_xml = etree.fromstring("""
            <notice xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys><preamble></preamble>
              <changeset>
                <change operation="added" label="1234-2">
                  <paragraph label="1234-2">An added paragraph</paragraph>
                </change>
              </changeset>
            </notice>""")
        original_xml = etree.fromstring("""
            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys>
              <preamble></preamble>
              <part label="1234">
                <content>
                  <paragraph label="1234-1">An existing paragraph</paragraph>
                  <paragraph label="1234-2">Another existing paragraph</paragraph>
                </content>
              </part>
            </regulation>""")
        with self.assertRaises(KeyError):
            process_changes(original_xml, notice_xml)

    def test_process_changes_added_interp(self):
        notice_xml = etree.fromstring("""
            <notice xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys><preamble></preamble>
              <changeset>
                <change operation="added" label="1234-Interp">
                  <interpretations label="1234-Interp">
                    <title>Supplement I to Part 1234</title>
                  </interpretations>
                </change>
              </changeset>
            </notice>""")
        original_xml = etree.fromstring("""
            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys>
              <preamble></preamble>
              <part label="1234">
                <content>
                  <subpart><content/></subpart>
                  <appendix label="1234-A"></appendix>
                </content>
              </part>
            </regulation>""")
        new_xml = process_changes(original_xml, notice_xml)
        new_interp = new_xml.find('.//{eregs}interpretations[@label="1234-Interp"]')
        self.assertNotEqual(new_interp, None)
        self.assertEqual(new_interp.getparent().index(new_interp), 2)

    def test_process_changes_added_before(self):
        notice_xml = etree.fromstring("""
            <notice xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys><preamble></preamble>
              <changeset>
                <change operation="added" label="1234-1" before="1234-2">
                  <paragraph label="1234-1">An added paragraph</paragraph>
                </change>
              </changeset>
            </notice>""")
        original_xml = etree.fromstring("""
            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys>
              <preamble></preamble>
              <part label="1234">
                <content>
                  <paragraph label="1234-2">An existing paragraph</paragraph>
                </content>
              </part>
            </regulation>""")
        new_xml = process_changes(original_xml, notice_xml)
        new_para = new_xml.find('.//{eregs}paragraph[@label="1234-1"]')
        self.assertEqual(new_para.getparent().index(new_para), 0)

    def test_process_changes_added_after(self):
        notice_xml = etree.fromstring("""
            <notice xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys><preamble></preamble>
              <changeset>
                <change operation="added" label="1234-2" after="1234-3">
                  <paragraph label="1234-2">An added paragraph</paragraph>
                </change>
              </changeset>
            </notice>""")
        original_xml = etree.fromstring("""
            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys>
              <preamble></preamble>
              <part label="1234">
                <content>
                  <paragraph label="1234-1">An existing paragraph</paragraph>
                  <paragraph label="1234-3">Another existing paragraph</paragraph>
                </content>
              </part>
            </regulation>""")
        new_xml = process_changes(original_xml, notice_xml)
        new_para = new_xml.find('.//{eregs}paragraph[@label="1234-2"]')
        self.assertEqual(new_para.getparent().index(new_para), 2)

    def test_process_changes_modified(self):
        notice_xml = etree.fromstring("""
            <notice xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys><preamble></preamble>
              <changeset>
                <change operation="modified" label="1234-1">
                  <paragraph label="1234-1">A modified paragraph</paragraph>
                </change>
              </changeset>
            </notice>""")
        original_xml = etree.fromstring("""
            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys>
              <preamble></preamble>
              <part label="1234">
                <content>
                  <paragraph label="1234-1">An existing paragraph</paragraph>
                </content>
              </part>
            </regulation>""")
        new_xml = process_changes(original_xml, notice_xml)
        mod_paras = new_xml.findall('.//{eregs}paragraph[@label="1234-1"]')
        self.assertEqual(len(mod_paras), 1)
        self.assertNotEqual(mod_paras[0], None)
        self.assertEqual("A modified paragraph", mod_paras[0].text)

    def test_process_changes_deleted(self):
        notice_xml = etree.fromstring("""
            <notice xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys><preamble></preamble>
              <changeset>
                <change operation="deleted" label="1234-1"></change>
              </changeset>
            </notice>""")
        original_xml = etree.fromstring("""
            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys>
              <preamble></preamble>
              <part label="1234">
                <content>
                  <paragraph label="1234-1">An existing paragraph</paragraph>
                </content>
              </part>
            </regulation>""")
        new_xml = process_changes(original_xml, notice_xml)
        del_paras = new_xml.findall('.//{eregs}paragraph[@label="1234-1"]')
        self.assertEqual(len(del_paras), 0)

    def test_process_changes_moved(self):
        notice_xml = etree.fromstring("""
            <notice xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys><preamble></preamble>
              <changeset>
                <change operation="moved" label="1234-1" parent="1234-Subpart-B"></change>
              </changeset>
            </notice>""")
        original_xml = etree.fromstring("""
            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys>
              <preamble></preamble>
              <part label="1234">
                <content>
                  <subpart label="1234-Subpart-A">
                    <content>
                      <paragraph label="1234-1">An existing paragraph</paragraph>
                    </content>
                  </subpart>
                  <subpart label="1234-Subpart-B">
                    <content>
                      <paragraph label="1234-2">Another existing paragraph</paragraph>
                    </content>
                  </subpart>
                </content>
              </part>
            </regulation>""")
        new_xml = process_changes(original_xml, notice_xml)
        moved_para = new_xml.find('.//{eregs}paragraph[@label="1234-1"]')
        self.assertEqual(moved_para.getparent().getparent().get('label'),
                         '1234-Subpart-B')
        self.assertEqual(moved_para.getparent().index(moved_para), 1)
        old_parent = new_xml.find('.//{eregs}subpart[@label="1234-Subpart-A"]/{eregs}content')
        self.assertEqual(len(old_parent.getchildren()), 0)

    def test_process_changes_moved_before(self):
        notice_xml = etree.fromstring("""
            <notice xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys><preamble></preamble>
              <changeset>
                <change operation="moved" label="1234-1" parent="1234-Subpart-B" before="1234-2"></change>
              </changeset>
            </notice>""")
        original_xml = etree.fromstring("""
            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys>
              <preamble></preamble>
              <part label="1234">
                <content>
                  <subpart label="1234-Subpart-A">
                    <content>
                      <paragraph label="1234-1">An existing paragraph</paragraph>
                    </content>
                  </subpart>
                  <subpart label="1234-Subpart-B">
                    <content>
                      <paragraph label="1234-2">Another existing paragraph</paragraph>
                    </content>
                  </subpart>
                </content>
              </part>
            </regulation>""")
        new_xml = process_changes(original_xml, notice_xml)
        moved_para = new_xml.find('.//{eregs}paragraph[@label="1234-1"]')
        self.assertEqual(moved_para.getparent().getparent().get('label'),
                         '1234-Subpart-B')
        self.assertEqual(moved_para.getparent().index(moved_para), 0)

    def test_process_changes_moved_after(self):
        notice_xml = etree.fromstring("""
            <notice xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys><preamble></preamble>
              <changeset>
                <change operation="moved" label="1234-1" parent="1234-Subpart-B" after="1234-2"></change>
              </changeset>
            </notice>""")
        original_xml = etree.fromstring("""
            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys></fdsys>
              <preamble></preamble>
              <part label="1234">
                <content>
                  <subpart label="1234-Subpart-A">
                    <content>
                      <paragraph label="1234-1">An existing paragraph</paragraph>
                    </content>
                  </subpart>
                  <subpart label="1234-Subpart-B">
                    <content>
                      <paragraph label="1234-2">Another existing paragraph</paragraph>
                      <paragraph label="1234-3">One more existing paragraph</paragraph>
                    </content>
                  </subpart>
                </content>
              </part>
            </regulation>""")
        new_xml = process_changes(original_xml, notice_xml)
        moved_para = new_xml.find('.//{eregs}paragraph[@label="1234-1"]')
        self.assertEqual(moved_para.getparent().getparent().get('label'),
                         '1234-Subpart-B')
        self.assertEqual(moved_para.getparent().index(moved_para), 1)

    def test_generate_diff_added(self):
        left_xml = etree.fromstring("""
            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys>
                <title>TEST CASE RUNNING ACT</title>
              </fdsys>
              <preamble>
                <cfr>
                  <section>1234</section>
                </cfr>
              </preamble>
              <part label="1234">
                <content>
                  <subpart>
                    <content>
                      <section label="1234-1" sectionNum="1">
                        <subject>§ 1234.1 Adding a paragraph</subject>
                      </section>
                    </content>
                  </subpart>
                </content>
              </part>
            </regulation>""")
        right_xml = etree.fromstring("""
            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys>
                <title>TEST CASE RUNNING ACT</title>
              </fdsys>
              <preamble>
                <cfr>
                  <section>1234</section>
                </cfr>
              </preamble>
              <part label="1234">
                <content>
                  <subpart>
                    <content>
                      <section label="1234-1" sectionNum="1">
                        <subject>§ 1234.1 Adding a paragraph</subject>
                        <paragraph label="1234-1-a" marker="(a)">
                          <title type="keyterm">Added.</title>
                          <content>A new paragraph</content>
                        </paragraph>
                      </section>
                    </content>
                  </subpart>
                </content>
              </part>
            </regulation>""")
        diff = generate_diff(left_xml, right_xml)
        self.assertEqual(len(diff.keys()), 1)
        self.assertTrue('1234-1-a' in diff)
        self.assertEqual(diff['1234-1-a']['op'], 'added')

    def test_generate_diff_modified(self):
        left_xml = etree.fromstring("""
            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys>
                <title>TEST CASE RUNNING ACT</title>
              </fdsys>
              <preamble>
                <cfr>
                  <section>1234</section>
                </cfr>
              </preamble>
              <part label="1234">
                <content>
                  <subpart>
                    <content>
                      <section label="1234-1" sectionNum="1">
                        <subject>§ 1234.1 Changing a paragraph</subject>
                        <paragraph label="1234-1-a" marker="(a)">
                          <title type="keyterm">Existing.</title>
                          <content>An existing paragraph</content>
                        </paragraph>
                      </section>
                    </content>
                  </subpart>
                </content>
              </part>
            </regulation>""")
        right_xml = etree.fromstring("""
            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys>
                <title>TEST CASE RUNNING ACT</title>
              </fdsys>
              <preamble>
                <cfr>
                  <section>1234</section>
                </cfr>
              </preamble>
              <part label="1234">
                <content>
                  <subpart>
                    <content>
                      <section label="1234-1" sectionNum="1">
                        <subject>§ 1234.1 Changing a paragraph</subject>
                        <paragraph label="1234-1-a" marker="(a)">
                          <title type="keyterm">Modified.</title>
                          <content>A modified paragraph</content>
                        </paragraph>
                      </section>
                    </content>
                  </subpart>
                </content>
              </part>
            </regulation>""")
        diff = generate_diff(left_xml, right_xml)
        self.assertEqual(len(diff.keys()), 1)
        self.assertTrue('1234-1-a' in diff)
        self.assertEqual(diff['1234-1-a']['op'], 'modified')

    def test_generate_diff_deleted(self):
        left_xml = etree.fromstring("""
            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys>
                <title>TEST CASE RUNNING ACT</title>
              </fdsys>
              <preamble>
                <cfr>
                  <section>1234</section>
                </cfr>
              </preamble>
              <part label="1234">
                <content>
                  <subpart>
                    <content>
                      <section label="1234-1" sectionNum="1">
                        <subject>§ 1234.1 Deleting a paragraph</subject>
                        <paragraph label="1234-1-a" marker="(a)">
                          <title type="keyterm">Existing.</title>
                          <content>An existing paragraph</content>
                        </paragraph>
                      </section>
                    </content>
                  </subpart>
                </content>
              </part>
            </regulation>""")
        right_xml = etree.fromstring("""
            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys>
                <title>TEST CASE RUNNING ACT</title>
              </fdsys>
              <preamble>
                <cfr>
                  <section>1234</section>
                </cfr>
              </preamble>
              <part label="1234">
                <content>
                  <subpart>
                    <content>
                      <section label="1234-1" sectionNum="1">
                        <subject>§ 1234.1 Deleting a paragraph</subject>
                      </section>
                    </content>
                  </subpart>
                </content>
              </part>
            </regulation>""")
        diff = generate_diff(left_xml, right_xml)
        self.assertEqual(len(diff.keys()), 1)
        self.assertTrue('1234-1-a' in diff)
        self.assertEqual(diff['1234-1-a']['op'], 'deleted')


#    def test_process_changes_toc_added(self):
#        # Note: Does not currently test Subpart adding
#        notice_xml = etree.fromstring("""
#            <notice xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
#              <fdsys></fdsys><preamble></preamble>
#              <changeset>
#                <change operation="added" label="1234-2">
#                  <section label="1234-2" sectionNum="2">
#                    <subject>1234.2 New Title</subject>
#                  </section>
#                </change>
#                <change operation="added" label="1234-Interp">
#                  <interpretations label="1234-Interp">
#                    <interpTitle>Supplement I to Part 1234</interpTitle>
#                  </interpretations>
#                </change>
#                <change operation="added" label="1234-B">
#                  <appendix appendixLetter="B" label="1024-B">
#                    <appendixTitle>Appendix B to Part 1234—Title parts</appendixTitle>
#                  </appendix>
#                </change>                
#             </changeset>
#            </notice>""")
#        original_xml = etree.fromstring("""
#            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
#              <fdsys></fdsys>
#              <preamble></preamble>
#              <part label="1234">
#                <tableOfContents>
#                  <tocSecEntry target="1234-1">
#                    <sectionNum>1</sectionNum>
#                    <sectionSubject>§ 1234.1 Designation.</sectionSubject>
#                  </tocSecEntry>
#                <tocAppEntry target="1234-A">
#                    <appendixLetter>A</appendixLetter>
#                    <appendixSubject>Appendix A - [Reserved]</appendixSubject>
#                  </tocAppEntry>
#                </tableOfContents>
#                <content>
#                  <subpart></subpart>
#                  <section label="1234-1"></section>
#                  <appendix label="1234-A"></appendix>
#                </content>
#              </part>
#            </regulation>""")
#        # Code for testing - on addition update, the TOC should get filled out with additional information
#        # and have 4 elements instead of 2 - the added Interp has no sibling so does not get added to the TOC
#        new_xml = process_changes(original_xml, notice_xml)
#        toc_root = new_xml.find('.//{eregs}tableOfContents')
#        num_children = len([el for el in toc_root.iterchildren()])
#        self.assertEqual(num_children, 4)
#
#
#    def test_process_changes_toc_modified(self):
#        # Note: Does not currently test Subpart modification
#        notice_xml = etree.fromstring("""
#            <notice xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
#              <fdsys></fdsys><preamble></preamble>
#              <changeset>
#                <change operation="modified" label="1234-1">
#                  <section label="1234-1" sectionNum="1">
#                    <subject>1234.1 New Title</subject>
#                  </section>
#                </change>
#                <change operation="modified" label="1234-Interp">
#                  <interpretations label="1234-Interp">
#                    <title>Supplement I to Part 1234</title>
#                  </interpretations>
#                </change>
#                <change operation="modified" label="1234-A">
#                  <appendix appendixLetter="A" label="1234-A">
#                    <appendixTitle>Appendix A to Part 1234—Title parts that are new</appendixTitle>
#                  </appendix>
#                </change>                
#             </changeset>
#            </notice>""")
#        original_xml = etree.fromstring("""
#            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
#              <fdsys></fdsys>
#              <preamble></preamble>
#              <part label="1234">
#                <tableOfContents>
#                  <tocSecEntry target="1234-1">
#                  </tocSecEntry>
#                  <tocInterpEntry target="1234-Interp">
#                  </tocInterpEntry>
#                  <tocAppEntry target="1234-A">
#                    <appendixLetter>A</appendixLetter>
#                    <appendixSubject>Appendix A - [Reserved]</appendixSubject>
#                  </tocAppEntry>
#                </tableOfContents>
#                <subpart></subpart>
#                <section label="1234-1"></section>
#                <interpretations label="1234-Interp"></interpretations>
#                <appendix label="1234-A"></appendix>
#              </part>
#            </regulation>""")
#        # Code for testing - on modification update, the TOC should get filled out with additional information
#        # and have 5 leaf-elements instead of 2
#        new_xml = process_changes(original_xml, notice_xml)
#        toc_root = new_xml.find('.//{eregs}tableOfContents')
#        num_children = sum([len(el) for el in toc_root.iterchildren()])
#        self.assertEqual(num_children, 5)
#
#
#    def test_process_changes_toc_deletion(self):
#        notice_xml = etree.fromstring("""
#            <notice xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
#              <fdsys></fdsys><preamble></preamble>
#              <changeset>
#                <change operation="deleted" label="1234-1"></change>
#              </changeset>
#            </notice>""")
#        original_xml = etree.fromstring("""
#            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
#              <fdsys></fdsys>
#              <preamble></preamble>
#              <part label="1234">
#                <tableOfContents>
#                  <tocSecEntry target="1234-1">
#                    <sectionNum>1</sectionNum>
#                    <sectionSubject>§ 1234.1 Designation.</sectionSubject>
#                  </tocSecEntry>
#                <tocAppEntry target="1234-A">
#                    <appendixLetter>A</appendixLetter>
#                    <appendixSubject>Appendix A - [Reserved]</appendixSubject>
#                  </tocAppEntry>
#                </tableOfContents>
#                <subpart></subpart>
#                <section label="1234-1"></section>
#                <appendix label="1234-A"></appendix>
#              </part>
#            </regulation>""")
#        new_xml = process_changes(original_xml, notice_xml)
#        del_sec = new_xml.findall('.//{eregs}section[@label="1234-1"]')
#        del_app = new_xml.findall('.//{eregs}appendix[@label="1234-A"]')
#        self.assertEqual(len(del_sec), 0)
#        self.assertEqual(len(del_app), 1)
