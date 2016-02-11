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

    def validate_term_references(self, tree, terms_layer,
            regulation_file, label=None):
        """ Validate term references. If label is given, only validate
            term references within that label. """

        problem_flag = False
        inf = inflect.engine()

        definitions = terms_layer['referenced']
        terms = set([(defn['term'], defn['reference']) for key, defn in definitions.iteritems()])
        cap_terms = set([(defn['term'][0].upper() + defn['term'][1:], defn['reference'])
                     for key, defn in definitions.iteritems()])
        terms = terms | cap_terms

        # Pick out our working section of the tree. If no label was
        # given, it *is* the tree.
        working_section = tree
        if label is not None:
            working_section = tree.find(
                    './/*[@label="{}"]'.format(label))

        paragraphs = working_section.findall('.//{eregs}paragraph') + \
                working_section.findall('.//{eregs}interpParagraph')
        ignore = set()
        always = set()

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
                                if term[0] not in always:
                                    while input_state not in ['y', 'n', 'i', 'a']:
                                        input_state = raw_input('(y)es/(n)o/(i)gnore this term/(a)lways correct: ')

                                if input_state in ['y', 'a'] or term[0] in always:
                                    problem_flag = True
                                    ref = '<ref target="{}" reftype="term">{}</ref>'.format(term[1], term_to_use)
                                    offsets_and_values.append((ref, [term_loc, term_loc + len(term_to_use)]))
                                    if input_state == 'a':
                                        always.add(term[0])
                                    
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

    def fix_omitted_cites(self, tree, regulation_file):
        """
        Try a simple fix to pick up internal citations that have been missed by regparser.
        There's no complicated grammar parsing going on here, just stupid regexing.
        :param tree: the xml tree
        :return:
        """
        paragraphs = tree.findall('.//{eregs}paragraph') + tree.findall('.//{eregs}interpParagraph')
        pattern = re.compile('([0-9]{4}\.([0-9]+)(\(([a-zA-Z]|[0-9])+\))+)')
        ignore = set()
        always = set()
        problem_flag = False

        def marker_to_target(marker_string):
            marker = marker_string.replace('.', '-')
            marker = marker.replace(')(', '-')
            marker = marker.replace('(', '-')
            marker = marker.replace(')', '')
            # marker = marker[:-1]
            return marker

        for paragraph in paragraphs:
            content = paragraph.find('{eregs}content')
            par_text = etree.tostring(content)
            matches = set([match[0] for match in pattern.findall(par_text)])
            label = paragraph.get('label')
            offsets_and_values = []

            # if matches != set([]):
            #     import ipdb; ipdb.set_trace()

            for match in matches:
                locations = set(find_all_occurrences(par_text, match))
                input_state = None
                for loc in locations:
                    if not enclosed_in_tag(par_text, 'ref', loc):
                        highlighted_par = colored(par_text[0:loc], 'yellow') + \
                                          colored(match, 'red') + \
                                          colored(par_text[loc + len(match):], 'yellow')

                        msg = colored('You appear to have used a reference to "{}" in {} without tagging it: \n'.format(
                              match, label), 'yellow') + \
                              '{}\n'.format(highlighted_par) + \
                              colored('Would you like the automatically fix this reference in the source?', 'yellow')
                        print(msg)
                        if match not in always:
                            while input_state not in ['y', 'n', 'i', 'a']:
                                input_state = raw_input('(y)es/(n)o/(i)gnore this reference/(a)lways correct: ')

                            if input_state in ['y', 'a'] or match in always:
                                problem_flag = True
                                ref = '<ref target="{}" reftype="internal">{}</ref>'.format(
                                    marker_to_target(match), match)
                                offsets_and_values.append((ref, [loc, loc + len(match)]))
                                if input_state == 'a':
                                    always.add(match)

                            elif input_state == 'i':
                                ignore.add(match)

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


    def headerize_interps(self, tree, regulation_file):
        paragraphs = tree.findall('.//{eregs}interpParagraph')
        change_flag = False

        for paragraph in paragraphs:
            title = paragraph.find('{eregs}title')
            content = paragraph.find('{eregs}content')
            label = paragraph.get('label')
            marker = paragraph.get('marker', '')
            target = paragraph.get('target', '')

            if title is None:
                current_par = etree.tostring(paragraph)
                print(colored(current_par, 'yellow'))
                response = None
                while response not in ['y', 'n']:
                    msg = colored('Do you want to titleize this paragraph?')
                    print(msg)
                    response = raw_input('(y)es/(n)o: ')
                if response.lower() == 'y':
                    response = None
                    content_text = content.text
                    first_period = content_text.find('.')
                    if first_period > -1:
                        title_string = content_text[:first_period + 1]
                        new_title = '<title>' + title_string + '</title>'
                        new_text = '<content>' + xml_node_text(content).replace(title_string, '').strip() + '</content>'
                        paragraph.insert(0, etree.fromstring(new_title))

                        #new_paragraph = '<interpParagraph label="{}" target="{}" marker="{}">\n'.format(label, target, marker)
                        #new_paragraph += new_title + '\n'
                        #new_paragraph += new_text + '\n</interpParagraph>'
                        #print(colored(new_paragraph, 'green'))

                        change_flag = True
                    else:
                        print(colored('Nothing to headerize!', 'red'))

    def insert_interp_markers(self, tree, regulation_file):
        """ Add in the markers for interp paragraphs in situations where 
            they're missing. """
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
