# -*- coding: utf-8 -*-

from unittest import TestCase

import lxml.etree as etree

from regulation.validation import EregsValidator, Severity

import settings


class EregsValidatorTests(TestCase):

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
