# -*- coding: utf-8 -*-
import lxml.etree as etree
import os
import settings
import shutil
import tempfile

from git import Repo
from unittest import TestCase

from regulation.validation import EregsValidator, Severity


class EregsValidatorTests(TestCase):
    GIT_URL = 'https://github.com/cfpb/regulations-schema.git'

    @classmethod
    def setUpClass(cls):
        cls.schemadir = tempfile.mkdtemp()
        Repo.clone_from(cls.GIT_URL, cls.schemadir)
        settings.XSD_FILE = os.path.join(cls.schemadir, 'src/eregs.xsd')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.schemadir, ignore_errors=True)

    def test_load_schema_works_if_schema_is_local(self):
        try:
            EregsValidator(settings.XSD_FILE).load_schema()
        except etree.XMLSchemaParseError:
            self.fail('schema should load successfully from local path')

    def test_load_schema_raises_if_local_schema_does_not_exist(self):
        with self.assertRaises(etree.XMLSchemaParseError):
            EregsValidator('/some/non/existent/path').load_schema()

    def test_load_schema_raises_if_remote_schema_does_not_exist(self):
        with self.assertRaises(etree.XMLSchemaParseError):
            EregsValidator('http://some.non/existent.url').load_schema()

    def test_validate_keyterms(self):
        tree = etree.fromstring("""
        <section xmlns="eregs" >
          <paragraph>
            <title type="keyterm">A Keyterm.</title>
            <content>A Keyterm. This paragraph should error.</content>
          </paragraph>
          <paragraph>
            <title type="keyterm">Another Keyterm.</title>
            <content>Keyterm. Fragment This one should warn.</content>
          </paragraph>
        </section>
        """)
        validator = EregsValidator(settings.XSD_FILE)
        validator.validate_keyterms(tree)

        self.assertEqual(len(validator.events), 3)

        self.assertEqual(validator.events[0].severity, Severity.ERROR)
        self.assertTrue('Duplicate keyterm' in validator.events[0].msg)

        self.assertEqual(validator.events[1].severity, Severity.WARNING)
        self.assertTrue('keyterm fragment' in validator.events[1].msg)

        self.assertEqual(validator.events[2].severity, Severity.WARNING)
        self.assertTrue('repeating keyterms' in validator.events[2].msg)

    def test_migrate_analysis_reg(self):
        tree = etree.fromstring("""
            <regulation xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys>
                <date>2015-11-17</date>
              </fdsys>
              <preamble>
                <documentNumber>2015-12345</documentNumber>
              </preamble>
              <part label="1234">
                <subpart>
                  <section label="1234-1">
                    <analysis>
                      <analysisSection>Some analysis</analysisSection>
                    </analysis>
                  </section>
                </subpart>
              </part>
            </regulation>""")
        validator = EregsValidator(settings.XSD_FILE)
        result = validator.migrate_analysis(tree)

        self.assertEqual(len(result.find('.//{eregs}analysis')), 1)

        analysis = result.find('.//{eregs}analysis')
        analysis_parent = analysis.getparent()
        analysis_section = analysis.find('{eregs}analysisSection')

        self.assertEqual(analysis_parent.tag, '{eregs}regulation')
        self.assertEqual(analysis_section.get('target'), '1234-1')
        self.assertEqual(analysis_section.get('notice'), '2015-12345')

    def test_migrate_analysis_notice(self):
        tree = etree.fromstring("""
            <notice xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys>
                <date>2015-11-17</date>
              </fdsys>
              <preamble>
                <documentNumber>2015-12345</documentNumber>
              </preamble>
              <changeset>
                <change operation="added" label="1234-5">
                  <paragraph label="1234-5">
                    <content/>
                    <analysis>
                      <analysisSection>Some addedanalysis</analysisSection>
                    </analysis>
                  </paragraph>
                </change>
              </changeset>
            </notice>""")
        validator = EregsValidator(settings.XSD_FILE)
        result = validator.migrate_analysis(tree)

        self.assertEqual(len(result.find('.//{eregs}analysis')), 1)

        analysis = result.find('.//{eregs}analysis')
        analysis_parent = analysis.getparent()
        analysis_section = analysis.find('{eregs}analysisSection')

        self.assertEqual(analysis_parent.tag, '{eregs}notice')
        self.assertEqual(analysis_section.get('target'), '1234-5')
        self.assertEqual(analysis_section.get('notice'), '2015-12345')

    def test_migrate_analysis_change_analysis_only(self):
        tree = etree.fromstring("""
            <notice xmlns="eregs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="eregs ../../eregs.xsd">
              <fdsys>
                <date>2015-11-17</date>
              </fdsys>
              <preamble>
                <documentNumber>2015-12345</documentNumber>
              </preamble>
              <changeset>
                <change operation="added" label="1234-2-Analysis" parent="1234-2">
                  <analysis label="1234-Analysis">
                    <analysisSection>An added analysis</analysisSection>
                  </analysis>
                </change>
              </changeset>
            </notice>""")
        validator = EregsValidator(settings.XSD_FILE)
        result = validator.migrate_analysis(tree)

        self.assertEqual(len(result.find('.//{eregs}analysis')), 1)

        analysis = result.find('.//{eregs}analysis')
        analysis_parent = analysis.getparent()
        analysis_section = analysis.find('{eregs}analysisSection')

        self.assertEqual(analysis_parent.tag, '{eregs}notice')
        self.assertEqual(analysis_section.get('target'), '1234-2')
        self.assertEqual(analysis_section.get('notice'), '2015-12345')

        # The empty change should've been deleted.
        self.assertEqual(len(result.findall('.//{eregs}change')), 0)

