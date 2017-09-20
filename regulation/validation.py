# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import copy
from enum import Enum
import operator
import re

from termcolor import colored, cprint
from lxml import etree
from .node import xml_node_text, find_all_occurrences, interpolate_string, enclosed_in_tag
from .changes import get_parent_label

import inflect
import re

import regulation.settings as settings


class Severity(Enum):
    """
    An Enum representing the severity of the event encountered upon parsing the regulation.
    """
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
    """
    A class encapsulating various validation strategies for ensuring correct output.
    It's mostly used for managing a small amount of state that doesn't change between
    functions, and also to keep track of events encountered during validation.
    """

    def __init__(self, xsd_file, ignore_errors=False):
        self.events = []
        self.xsd_file = xsd_file
        self.schema = self.load_schema()
        self.ignore_errors = ignore_errors

    def load_schema(self):
        """
        Load the XSD file used to validate the reg.

        :param: None.
        :return: :class:`etree.XMLSchema`: the schema object used to validate the reg.
        """
        try:
            return etree.XMLSchema(file=self.xsd_file)
        except etree.XMLSchemaParseError:
            cprint(
                'Error occurred when reading schema file {}; did you forget '
                'to set settings.XSD_FILE to a local or remote path '
                'containing the eregs schema?'.format(self.xsd_file), 'red'
            )
            raise

    def validate_reg(self, tree):
        """
        Validate the XML tree according to ``self.schema``. After validation, ``self.events``
        contains all significant events encountered.

        :param tree: the root of the XML tree.
        :type tree: :class:`etree.Element`
        :return: None
        """
        if self.schema is not None:
            try:
                self.schema.assertValid(tree)
                validation_ok = EregsValidationEvent(
                    'XML Validated!', severity=Severity(Severity.OK))
                self.events.append(validation_ok)
            except Exception as ex:
                doc_number = tree.find('{eregs}preamble').find('{eregs}documentNumber').text
                msg = 'Error validating regs XML for part {}!: {}'.format(doc_number, ex)
                validation_ex = EregsValidationEvent(
                    msg, severity=Severity(Severity.CRITICAL))
                self.events.append(validation_ex)

        else:
            raise EregsValidationEvent(
                'Attempting to validate with empty schema!',
                severity=Severity(Severity.CRITICAL))

    def validate_keyterms(self, tree, notice_tree=None):
        """
        Make sure that keyterm titles aren't repeated in the content of
        the paragraph they belong to. After validation, ``self.events``
        contains all significant events encountered.

        :param tree: the root of the XML tree.
        :type tree: :class:`etree.Element`
        :returns: None.
        """
        problem_flag = False
        keyterms = tree.findall('.//*[@type="keyterm"]')

        keyterm_events = []

        for keyterm in keyterms:
            # Get the parent and its label
            parent = keyterm.getparent()
            label = parent.get('label')

            # If we're given a notice tree, and the label doesn't appear
            # in the notice, just ignore it.
            if notice_tree is not None:
                in_notice = notice_tree.findall('.//*[@label="' + label + '"]')
                if len(in_notice) == 0:
                    continue

            # Get just the text of the keyterm. If the keyterm has other
            # tags, like a reference, we need to strip those.
            keyterm_text = keyterm.text
            if len(keyterm) > 0:
                # Note: We don't want to modify the tree
                keyterm = copy.deepcopy(keyterm)
                keyterm_text = etree.strip_tags(keyterm, '{*}*')

            # Strip the usual trailing period, just to be sure.
            keyterm_text = re.sub(r'[\.]', '', keyterm_text)

            # Get the content element of the paragraph. Strip any other
            # tags, as above.
            content = parent.find('{eregs}content')
            content_text = content.text
            if len(content) > 0:
                # Note: We don't want to modify the tree
                content = copy.deepcopy(content)
                etree.strip_tags(content, '{*}*')

            if content.text is not None:
                # If the keyterm is there outright, error.
                if content.text.startswith(keyterm.text):
                    msg = 'Duplicate keyterm: ' \
                          'in {} the keyterm "{}" appears both in the title ' \
                          'and the content.'.format(label, keyterm.text)
                    event = EregsValidationEvent(
                        msg, severity=Severity(Severity.ERROR))
                    keyterm_events.append(event)
                    problem_flag = True

                # Next we check for possible fragments of the keyterm
                # that could be left in.
                elif any(w for w in keyterm_text.split()
                        if content.text.startswith(w)):
                    msg = 'Possible keyterm fragment: ' \
                          'in {} a fragment of keyterm "{}" appears in ' \
                          'the content.'.format(label, keyterm.text)
                    event = EregsValidationEvent(
                        msg, severity=Severity(Severity.WARNING))
                    keyterm_events.append(event)
                    problem_flag = True

        self.events = self.events + keyterm_events

        if problem_flag:
            msg = 'There were {} potential problems with repeating ' \
                  'keyterms.'.format(
                    len(keyterm_events))
            event = EregsValidationEvent(msg, Severity(Severity.WARNING))
        else:
            msg = 'No keyterm titles appear to be repeated'
            event = EregsValidationEvent(msg, Severity(Severity.OK))

        self.events.append(event)

    def validate_terms(self, tree, terms_layer):
        """
        Validate the tree to make sure that all terms referenced in the
        terms layer are defined somewhere in the tree. After validation, ``self.events``
        contains all significant events encountered.

        :param tree: the root of the XML tree of the regulation.
        :type tree: :class:`etree.Element`
        :param terms_layer: the dictionary of terms
        :type terms_layer: :class:`collections.OrderedDict`
        :return: None.
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
            regulation_file, label=None, term=None, notice=None,
            ignore_phrases=[]):
        """
        Validate term references. If label is given, only validate
        term references within that label. If term is given, only
        validate references to that term. If notice is given as a notice
        xml tree, the modified paragraph content will be writen back to
        the notice, either to an existing paragraph or as a modified
        change. Prompts to overwrite original file.

        :param tree: the root of the XML tree.
        :type tree: :class:`etree.Element`
        :param terms_layer: the layer dictionary produced by :func:`regulation.tree.build_term_layer`.
        :type terms_layer: :class:`collections.OrderedDict`
        :param regulation_file: path to the regulation or notice file to which to save changes.
        :type regulation_file: :class:`str`
        :param label: check the contents of this label within the regulation tree (entire reg tree if None)
        :type label: :class:`str`
        :param term: the term the check (all if None)
        :type term: :class:`str`
        :param notice: the root of a notice XML tree
        :type notice: :class:`etree.Element`
        :return: None
        """

        problem_flag = False
        inf = inflect.engine()

        definitions = terms_layer['referenced']
        terms = set([(defn['term'], defn['reference']) for key, defn in definitions.items()])
        cap_terms = set([(defn['term'][0].upper() + defn['term'][1:], defn['reference'])
                     for key, defn in definitions.iteritems()])
        terms = terms | cap_terms
        if term is not None:
            try:
                reference = next((defn['reference'] for key, defn in
                    definitions.items() if defn['term'] == term))
            except StopIteration:
                print(colored("{} is not a defined term".format(term),
                    'red'))
                return
            terms = set([(term, reference),
                         (term[0].upper() + term[1:], reference)])

        # Pick out our working section of the tree. If no label was
        # given, it *is* the tree.
        working_section = tree
        if label is not None:
            working_section = tree.find(
                    './/*[@label="{}"]'.format(label))

        paragraphs = working_section.findall('.//{eregs}paragraph') + \
                     working_section.findall('.//{eregs}interpParagraph')
        if len(paragraphs) == 0 and 'aragraph' in working_section.tag:
            paragraphs = [working_section,]

        ignore = set()
        always = set()

        for paragraph in paragraphs:
            content = paragraph.find('.//{eregs}content')
            par_text = unicode(etree.tostring(content,
                encoding='UTF-8'))
            label = paragraph.get('label')
            offsets_and_values = []

            for term in terms:
                if term[0] not in ignore and label != term[1]:
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
                print(highlight)

                # If we were not given a notice, just replace the
                # paragraph in the reg tree and move on.
                new_content = etree.fromstring(new_par_text)
                if notice is None:
                    paragraph.replace(content, new_content)
                else:
                    # Otherwise, look for this paragraph in the notice.
                    # If it doesn't exist there, add a modified change
                    # for it.
                    notice_paragraph = notice.find('.//{tag}[@label="{label}"]'.format(
                        tag=paragraph.tag, label=label))

                    if notice_paragraph is None:
                        print(colored('adding change for paragraph in notice\n', attrs=['bold']))
                        changeset = notice.find('.//{eregs}changeset')
                        change = etree.SubElement(changeset, 'change')
                        change.set('operation', 'modified')
                        change.set('label', label)
                        change.append(paragraph)
                    else:
                        print(colored('replacing content in notice paragraph\n', attrs=['bold']))
                        notice_content = notice_paragraph.find('.//{eregs}content')
                        notice_paragraph.replace(notice_content, new_content)

        if problem_flag:
            print(colored('The tree has been altered! Do you want to write the result to disk?'))
            answer = None
            while answer not in ['y', 'n']:
                answer = raw_input('Save? y/n: ')
            if answer == 'y':
                with open(regulation_file, 'w') as f:
                    print('Writing ' + regulation_file + '...')
                    if notice is None:
                        f.write(etree.tostring(tree, pretty_print=True, encoding='UTF-8'))
                    else:
                        # If notice was given, presume that the file
                        # path given is to the notice, not the
                        # regulation.
                        f.write(etree.tostring(notice, pretty_print=True, encoding='UTF-8'))

    def validate_internal_cites(self, tree, internal_cites_layer):
        """
        Validate the tree to make sure that all internal cites refer to
        an existing label. After validation, ``self.events``
        contains all significant events encountered.

        :param tree: the root of the XML tree of the reg.
        :type tree: :class:`etree.Element`
        :param internal_cites_layer: the dictionary of internal cites.
        :type internal_cites_layer: :class:`collections.OrderedDict`
        :return: None

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
        There's no complicated grammar parsing going on here, just stupid regexing. Prompts to overwrite original file.

        :param tree: the root of the XML tree.
        :type tree: :class:`etree.Element`
        :param regulation_file: path to the regulation file to which to save changes.
        :type regulation_file: :class:`str`
        :return: None
        """
        paragraphs = tree.findall('.//{eregs}paragraph') + tree.findall('.//{eregs}interpParagraph')
        pattern = re.compile('([0-9]{4}\.([0-9]+)(\(([a-zA-Z]+|[0-9])+\))+)')
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

            for match in matches:
                locations = set(find_all_occurrences(par_text, match, boundary=False))
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
        """
        Interactively headerize interps that are missing titles. Prompts to overwrite original file.

        :param tree: the root of the XML tree.
        :type tree: :class:`etree.Element`
        :param regulation_file: path to the regulation file to which to save changes.
        :type regulation_file: :class:`str`
        :return: None
        """
        paragraphs = tree.findall('.//{eregs}interpParagraph')
        change_flag = False

        for paragraph in paragraphs:
            title = paragraph.find('{eregs}title')
            content = paragraph.find('{eregs}content')
            label = paragraph.get('label')
            marker = paragraph.get('marker', '')
            target = paragraph.get('target', '')

            if title is None:
                current_par = etree.tostring(paragraph, encoding='UTF-8')
                print(colored(current_par, 'yellow'))
                response = None
                while response not in ['y', 'n']:
                    msg = colored('Do you want to titleize this paragraph?', 'red')
                    print(msg)
                    response = raw_input('(y)es/(n)o: ')
                if response.lower() == 'y':
                    #import ipdb; ipdb.set_trace()
                    response = None
                    content_text = etree.tostring(content)
                    first_angle = content_text.find('>')
                    close_content = content_text.find('</content>')
                    remainder = content_text[first_angle + 1:close_content]
                    first_period = remainder.find('.')
                    if first_period > -1:
                        title_string = remainder[:first_period + 1]
                        new_title = '<title>' + title_string + '</title>'
                        elem = etree.fromstring(new_title)
                        new_title = '<title>' + xml_node_text(elem) + '</title>'
                        new_text = '<content>' + remainder.replace(title_string, '').strip() + '</content>'
                        paragraph.insert(0, etree.fromstring(new_title))
                        paragraph.replace(content, etree.fromstring(new_text))
                        new_paragraph = '<interpParagraph label="{}" target="{}" marker="{}">\n'.format(label, target, marker)
                        new_paragraph += new_title + '\n'
                        new_paragraph += new_text + '\n</interpParagraph>'
                        print(colored(new_paragraph, 'green'))
                        change_flag = True
                    else:
                        print(colored('Nothing to headerize!', 'red'))
        if change_flag:
            print(colored('The tree has been altered! Do you want to write the result to disk?', 'red'))
            answer = None
            while answer not in ['y', 'n']:
                answer = raw_input('Save? y/n: ')
            if answer == 'y':
                with open(regulation_file, 'w') as f:
                    f.write(etree.tostring(tree, pretty_print=True, encoding='UTF-8'))

    def insert_interp_markers(self, tree, regulation_file):
        """
        Add in the markers for interp paragraphs in situations where
        they're missing. Overwrites original file.

        :param tree: the root of the XML tree.
        :type tree: :class:`etree.Element`
        :param regulation_file: path to the regulation file to which to save changes.
        :type regulation_file: :class:`str`
        :return: None
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
            f.write(etree.tostring(tree, pretty_print=True, encoding='UTF-8'))

    @property
    def is_valid(self):
        return all(e.severity == Severity.OK for e in self.events)

    @property
    def has_critical_errors(self):
        return any(e.severity == Severity.CRITICAL for e in self.events)

    def validate_interp_targets(self, tree, regulation_file, label=None):
        """
        Validate interpretation targets within a given label with
        the option to write corrected targets out to the
        regulation_file. Prompts to overwrite original file.

        :param tree: the root of the XML tree.
        :type tree: :class:`etree.Element`
        :param regulation_file: path to the regulation file to which to save changes.
        :type regulation_file: :class:`str`
        :param label: the string of the label whose internal interps to validate.
         Defaults to the ``<interpretations>`` tag.
        :type label: :class:`str`
        :return: None
        """

        problem_flag = False

        # Find all paragraphs with a target attribute
        paragraphs = tree.findall(
                './/{eregs}interpParagraph[@target]')


        for paragraph in paragraphs:
            target = paragraph.get('target')
            label = paragraph.get('label')

            # If the label doesn't end with '-Interp' it shouldn't have
            # a target.
            if not label.endswith('-Interp') and target is not None:
                problem_flag = True
                print(colored('Removing bad target {} in {}'.format(
                        target, label), 'yellow'))
                del paragraph.attrib['target']
                continue

            # Break down the label and figure out the paragraph the
            # paragraph should be assigned to. If it doesn't match the
            # target, it's a bad target.
            label_target = label[:label.find('-Interp')]
            if label_target != target:
                problem_flag = True
                print(colored('Fixing bad target {} in {}'.format(
                        target, label), 'yellow'))
                paragraph.set('target', label_target)
                continue

            print(colored('Leaving good target {} in {}'.format(
                    target, label), 'green'))

        if problem_flag:
            print(colored('The tree has been altered! Do you want to'
                'write the result to disk?', 'red'))
            answer = None
            while answer not in ['y', 'n']:
                answer = raw_input('Save? y/n: ')
            if answer == 'y':
                with open(regulation_file, 'w') as f:
                    f.write(etree.tostring(tree, pretty_print=True))

    def remove_duplicate_changes(self, tree, notice_file, label=None):
        """
        Look through notice change elements and find children that have
        the same operation as their parent (in which case the change to
        the child is included in the parent) and eliminate the duplicate
        child change.
        """
        # Map change operations to colors
        OP_COLORS = {'added': 'green',
                     'modified': 'yellow',
                     'moved': 'yellow',
                     'deleted': 'red'}

        dups_flag = False

        # Get the changes by label
        change_elms = tree.findall('.//{eregs}change')
        changes = {c.get('label'): c for c in change_elms}

        if label is not None:
            changes = {c.get('label'): c for c in change_elms
                       if c.get('label') == label}

        unresolved_dups = []
        for label, change in sorted(changes.items(),
                key=operator.itemgetter(0)):
            op = change.get('operation')

            parent = change.get('parent')
            if parent is None:
                parent = '-'.join(get_parent_label(label.split('-')))

            if parent in changes.keys():
                parent_op = changes[parent].get('operation')
                change_string = colored('{}({})'.format(label, op),
                        OP_COLORS[op])
                parent_string = colored('{}({})'.format(parent,
                    parent_op), OP_COLORS[parent_op])

                # Don't automatically remove "modified" or "moved"
                # operations. Let the user resolve those.
                if op not in ("modified", "moved") and \
                        op == parent_op:
                    print('{change} will be changed by parent '
                          '{parent_change} change. Do you want to '
                          'remove {change}?'.format(
                              change=change_string,
                              parent_change=parent_string))
                    change.getparent().remove(change)
                    dups_flag = True
                elif op != "moved":
                    unresolved_dups.append((change_string, parent_string))

        if dups_flag:
            print(colored('The changes have been altered! Do you want '
                          'to write the result to disk?', 'red'))
            answer = None
            while answer not in ['y', 'n']:
                answer = raw_input('Save? y/n: ')
            if answer == 'y':
                with open(notice_file, 'w') as f:
                    f.write(etree.tostring(tree, pretty_print=True, encoding='UTF-8'))

        if len(unresolved_dups) > 0:
            print(colored(str(len(unresolved_dups)), 'red'),
                  'potentially duplicate changes remain unresolved:')
            for change, parent in unresolved_dups:
                print(change, '/', parent)

    def remove_empty_refs(self, tree, xml_file):
        """
        Delete empty references, which are sometimes spuriously generated by the eCFR parser.
        """
        references = tree.findall('.//{eregs}ref')
        for ref in references:
            if ref.text is None or ref.text.strip() == '':
                ref.getparent().remove(ref)
                print('Removing empty reference:', colored(etree.tostring(ref), 'red'))

        print('The tree has been altered!')
        answer = None
        while answer not in ['y', 'n']:
            answer = raw_input('Save? y/n: ')
        if answer == 'y':
            with open(xml_file, 'w') as f:
                f.write(etree.tostring(tree, pretty_print=True, encoding='UTF-8'))

    def migrate_analysis(self, tree, regulation_file=None):
        """ For the given tree, break all out analysis and migrate it to
            a top-level analysis element with targets for the original
            labels it belongs to. The resulting file will be writen out
            to the given file. This will work on both regulation trees
            and notice trees. """

        # Find all analysis elements
        analyses = tree.findall('.//{eregs}analysis')

        if len(analyses) == 0:
            return tree
        if len(analyses) == 1 and \
                analyses[0].getparent().tag in ('{eregs}notice', '{eregs}regulation'):
            return tree

        # Create the top level analysis element
        analysis = etree.SubElement(tree, '{eregs}analysis')

        # Get metadata for individual analysisSections
        document_number = tree.find('.//{eregs}documentNumber').text
        publication_date = tree.find('.//{eregs}fdsys/{eregs}date').text

        # Get the analysis parents (targets)
        for old_analysis in analyses:
            parent = old_analysis.getparent()
            analysis_section = old_analysis.find('{eregs}analysisSection')

            # Add the analysis elements to the top-level analysis
            analysis.append(analysis_section)

            # Remove the old analysis element
            old_analysis.getparent().remove(old_analysis)

            # Get and set the analysis section's target
            target = parent.get('label')
            if parent.tag == '{eregs}change':
                target = parent.get('parent')
                # If the parent is a change, it should be empty and can
                # also be deleted
                if len(parent) == 0:
                    parent.getparent().remove(parent)

            analysis_section.set('target', target)
            analysis_section.set('notice', document_number)
            analysis_section.set('date', publication_date)

            print(colored('Migrated analysis for ' + target + '.', 'green'))

        if regulation_file is not None:
            with open(regulation_file, 'w') as f:
                f.write(etree.tostring(tree, pretty_print=True, encoding='UTF-8'))

        return tree

