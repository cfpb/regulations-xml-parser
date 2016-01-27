# -*- coding: utf-8 -*-
from __future__ import print_function

from enum import Enum

from termcolor import colored, cprint
from lxml import etree
from .node import xml_node_text, find_all_occurrences, interpolate_string, enclosed_in_tag

import inflect
import re

import regulation.settings as settings


class Severity(Enum):

    OK = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4

    def __str__(self):
        return colored('{}:'.format(self.name), self.color)

    @property
    def color(self):
        colors = {Severity['OK']: 'green',
                  Severity['INFO']: 'cyan',
                  Severity['WARNING']: 'yellow',
                  Severity['ERROR']: 'red',
                  Severity['CRITICAL']: 'red'}

        return colors[self]

    @property
    def symbol(self):
        symbols = {Severity['OK']: u'\u2713',
                   Severity['INFO']: '',
                   Severity['WARNING']: u'\u26a0',
                   Severity['ERROR']: u'\u2717',
                   Severity['CRITICAL']: u'\u2717'}
        return symbols[self]


class EregsValidationEvent(Exception):

    def __init__(self, msg, severity=Severity(Severity.CRITICAL)):
        super(EregsValidationEvent, self).__init__(msg)
        self.severity = severity
        self.msg = msg

    def __str__(self):
        msg = str(self.severity) + colored(' {} {}'.format(
            self.msg, self.severity.symbol), self.severity.color)
        return msg


class EregsValidator:

    def __init__(self, xsd_file, ignore_errors=False):
        self.events = []
        self.xsd_file = xsd_file
        self.schema = self.load_schema()
        self.ignore_errors = ignore_errors

    def load_schema(self):
        try:
            schema = etree.XMLSchema(file=self.xsd_file)

        except Exception as ex:
            cprint('Exception occurred when reading file: {0!s}'.format(
                ex), 'red')
            return None

        return schema

    def validate_reg(self, tree):
        if self.schema is not None:
            try:
                self.schema.assertValid(tree)
                validation_ok = EregsValidationEvent(
                    'XML Validated!', severity=Severity(Severity.OK))
                self.events.append(validation_ok)
            except Exception as ex:
                msg = 'Error validating regs XML!: {}'.format(ex)
                validation_ex = EregsValidationEvent(
                    msg, severity=Severity(Severity.CRITICAL))
                self.events.append(validation_ex)

        else:
            raise EregsValidationEvent(
                'Attempting to validate with empty schema!',
                severity=Severity(Severity.CRITICAL))

    def validate_terms(self, tree, terms_layer):
        """
        Validate the tree to make sure that all terms referenced in the
        terms layer are defined somewhere in the tree.

        :param tree: the xml tree of the regulation
        :param terms_layer: the dictionary of terms
        :return: true/false
        """

        inf = inflect.engine()

        problem_flag = False

        definitions = terms_layer['referenced']
        def_locations = []
        # print json.dumps(definitions, indent=4)
        for key, defn in definitions.items():
            term = defn['term']
            defined_in = defn['reference']
            def_locations.append(defined_in)
            event = EregsValidationEvent('TERM: "{}" defined in: {}'.format(
                term, defined_in), severity=Severity(Severity.INFO))
            self.events.append(event)

        paragraphs = tree.findall('.//{eregs}paragraph') + \
            tree.findall('.//{eregs}interpParagraph')

        for paragraph in paragraphs:
            content = paragraph.find('{eregs}content')
            refs = content.findall('.//{eregs}ref[@reftype="term"]')
            label = paragraph.get('label')
            for ref in refs:
                term = (ref.text or '').lower()

                if term not in settings.SPECIAL_SINGULAR_NOUNS and \
                        inf.singular_noun(term):
                    term = inf.singular_noun(term)

                location = ref.get('target') or ''

                key = '{}:{}'.format(term, location)

                if key not in definitions:
                    # print key, label, location
                    msg = 'MISSING DEFINITION: ' \
                          'in {} the term "{}" was referenced; it is '\
                          'expected to be defined in {} but is not.'.format(
                              label, term, location)
                    event = EregsValidationEvent(
                        msg, severity=Severity(Severity.WARNING))
                    self.events.append(event)
                    problem_flag = True

        if problem_flag:
            msg = 'There were some problems with references to terms. ' \
                  'While these are usually not fatal, they can result ' \
                  'in the wrong text being highlighted or incorrect ' \
                  'links within the regulation text.'
            event = EregsValidationEvent(msg, Severity(Severity.WARNING))
        else:
            msg = 'All term references in the text point to existent ' \
                  'definitions.'
            event = EregsValidationEvent(msg, Severity(Severity.OK))

        self.events.append(event)

    def validate_term_references(self, tree, terms_layer, regulation_file):

        problem_flag = False
        inf = inflect.engine()

        definitions = terms_layer['referenced']
        terms = [(defn['term'], defn['reference']) for key, defn in definitions.iteritems()]
        cap_terms = [(defn['term'][0].upper() + defn['term'][1:], defn['reference'])
                     for key, defn in definitions.iteritems()]

        terms = terms + cap_terms

        paragraphs = tree.findall('.//{eregs}paragraph') + tree.findall('.//{eregs}interpParagraph')
        ignore = set()

        for paragraph in paragraphs:
            content = paragraph.find('.//{eregs}content')
            par_text = etree.tostring(content)
            label = paragraph.get('label')
            offsets_and_values = []

            for term in terms:
                if term[0] not in ignore:
                    input_state = None
                    term_locations = set(find_all_occurrences(par_text, term[0]))
                    plural_term = inf.plural(term[0])
                    plural_term_locations = set(find_all_occurrences(par_text, plural_term))
                    unmarked_locs = list(plural_term_locations | term_locations ^ plural_term_locations)
                    for term_loc in unmarked_locs:
                        if term_loc in plural_term_locations:
                            term_to_use = plural_term
                        elif term_loc in term_locations:
                            term_to_use = term[0]
                        if not enclosed_in_tag(par_text, 'ref', term_loc) and not enclosed_in_tag(par_text, 'def', term_loc):
                            if input_state is None:

                                highlighted_par = colored(par_text[0:term_loc], 'yellow') + \
                                                  colored(term_to_use, 'red') + \
                                                  colored(par_text[term_loc + len(term_to_use):], 'yellow')

                                msg = colored('You appear to have used the term "{}" in {} without referencing it: \n'.format(term_to_use, label), 'yellow') + \
                                      '{}\n'.format(highlighted_par) + \
                                      colored('Would you like the automatically fix this reference in the source?', 'yellow')
                                print(msg)
                                while input_state not in ['y', 'n', 'i']:
                                    input_state = raw_input('(y)es/(n)o/(i)gnore this term: ')

                                if input_state == 'y':
                                    problem_flag = True
                                    ref = '<ref target="{}" reftype="term">{}</ref>'.format(term[1], term_to_use)
                                    offsets_and_values.append((ref, [term_loc, term_loc + len(term_to_use)]))
                                elif input_state == 'i':
                                    ignore.add(term[0])

                                input_state = None

            if offsets_and_values != []:
                offsets_and_values = sorted(offsets_and_values, key=lambda x: x[1][0])
                values, offsets = zip(*offsets_and_values)
                new_par_text = interpolate_string(par_text, offsets, values)
                highlight = interpolate_string(par_text, offsets, values, colorize=True)
                new_content = etree.fromstring(new_par_text)
                paragraph.replace(content, new_content)
                print(highlight)


        if problem_flag:
            print(colored('The tree has been altered! Do you want to write the result to disk?'))
            answer = None
            while answer not in ['y', 'n']:
                answer = raw_input('Save? y/n: ')
            if answer == 'y':
                with open(regulation_file, 'w') as f:
                    f.write(etree.tostring(tree, pretty_print=True))

    def validate_internal_cites(self, tree, internal_cites_layer):
        """
        Validate the tree to make sure that all internal cites refer to
        an existing label.
        :param tree: xml tree of the reg
        :param internal_cites_layer: the dictionary of internal cites
        :return: true/false
        """
        problem_flag = False

        # cites = tree.findall('.//{eregs}ref[@reftype="internal"]')
        labeled_elements = tree.findall('.//')
        labels = [elem.get('label') for elem in labeled_elements
                  if elem.get('label') is not None]

        for label, cites in internal_cites_layer.items():
            if label not in labels:
                msg = 'NONEXISTENT LABEL: ' \
                      'Internal layer attempts to reference label {} ' \
                      'but that label does not exist in the XML! ' \
                      'Something is very wrong!'
                event = EregsValidationEvent(msg, Severity(Severity.ERROR))
                self.events.append(event)
                problem_flag = True

            for cite in cites:
                citation = '-'.join(cite['citation'])
                if citation not in labels:
                    msg = 'NONEXISTENT CITATION: ' \
                          'There is a reference to label {} in {} but ' \
                          'that referenced label does not exist. ' \
                          'This can cause problems!'.format(citation, label)
                    event = EregsValidationEvent(msg, Severity(Severity.ERROR))
                    self.events.append(event)
                    problem_flag = True

        if problem_flag:
            msg = 'There were some problems with the internal ' \
                  'citations. While these are not necessarily ' \
                  'not fatal, they can result in non-functioning ' \
                  'links and possibly key errors in regsite.'
            event = EregsValidationEvent(msg, Severity(Severity.ERROR))
        else:
            msg = 'All internal references in the text point to ' \
                  'existing labels.'
            event = EregsValidationEvent(msg, Severity(Severity.OK))

        self.events.append(event)

    def insert_interp_markers(self, tree, regulation_file):
        """Add in the markers for interp paragraphs in situations where they're missing.
        """

        paragraphs = tree.findall('.//{eregs}interpParagraph')
        for paragraph in paragraphs:
            label = paragraph.get('label')
            split_label = label.split('-')
            if 'Interp' in split_label:
                index = split_label.index('Interp')
                if index + 1 < len(split_label) and split_label[index + 1].isdigit():
                    marker = split_label[-1] + '.'
                    paragraph.set('marker', marker)

        with open(regulation_file, 'w') as f:
            f.write(etree.tostring(tree, pretty_print=True))

    @property
    def is_valid(self):
        for error in self.events:
            if error.severity != Severity.OK:
                return False
        return True
