# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from copy import deepcopy
import itertools
import logging

from lxml import etree

# Import regparser here with the eventual goal of breaking off the parts
# we're using in the RegML parser into a library both can share.
from regparser.tree.paragraph import p_levels
from regparser.tree.struct import FrozenNode
from regparser.diff.tree import changes_between

import string

def roman_nums():
    """Generator for roman numerals."""
    mapping = [(1, 'i'), (4, 'iv'), (5, 'v'), (9, 'ix'),
               (10, 'x'), (40, 'xl'), (50, 'l'), (90, 'xc'),
               (100, 'c'), (400, 'cd'), (500, 'd'), (900, 'cm'),
               (1000, 'm')]
    i = 1
    while True:
        next_str = ''
        remaining_int = i
        remaining_mapping = list(mapping)
        while remaining_mapping:
            (amount, chars) = remaining_mapping.pop()
            while remaining_int >= amount:
                next_str += chars
                remaining_int -= amount
        yield next_str
        i += 1

p_levels = [
    list(string.ascii_lowercase),
    [str(i) for i in range(1, 51)],
    list(itertools.islice(roman_nums(), 0, 50)),
    list(string.ascii_uppercase),
    ['<E T="03">' + str(i) + '</E>' for i in range(1, 51)],
    ['<E T="03">' + i + '</E>'
     for i in itertools.islice(roman_nums(), 0, 50)]
]

from regulation.tree import build_reg_tree


logger = logging.getLogger(__name__)

TAGS_WITH_SUBCONTENT = ["{eregs}part", "{eregs}subpart"]


def get_parent_label(label_parts):
    """ Determine the parent label for the given label part list. """
    parent_label = None

    # It can't have a parent if it's only one part
    if len(label_parts) <= 1:
        return parent_label

    # If it's the interps for the whole part, return the part
    if len(label_parts) == 2:
        return label_parts[:1]

    # Not an interpretation label. This is easy.
    parent_label = label_parts[0:-1]

    if label_parts[-1] == 'Interp':
        # It's the whole interp for the label. Get the parent and
        # add Interp again.
        parent_label = get_parent_label(parent_label)
        parent_label.append('Interp')

    # Subparts are also special and their parent should be the label
    # until the "Subpart" portion
    if "Subpart" in label_parts:
        parent_label = label_parts[:label_parts.index("Subpart")]

    return parent_label


def get_sibling_label(label_parts):
    """ Determine the preceding sibling label for the given label part
        list, if one exists. """
    sibling_label = []

    # It can't have a sibling if it's only one part
    if len(label_parts) <= 1:
        return sibling_label

    # Start with the parent label. We don't funk interp-resolution here
    # so we won't use the get_parent_label function.
    sibling_label = label_parts[0:-1]
    last_part = label_parts[-1]
    if label_parts[-1] == 'Interp':
        # If this is an interpretation, we'll find the original marker's
        # sibling and then add 'Interp' to it at the end.
        last_part = label_parts[-2]
        sibling_label = label_parts[0:-2]

    # Now find the preceding marker for the last marker.
    for level in reversed(p_levels):
        if last_part in level:
            index = level.index(last_part)
            if index > 0:
                sibling_label.append(level[index - 1])
            else:
                # There is no preceding sibling
                return None
            break

    if label_parts[-1] == 'Interp':
        # Restore 'Interp' to the sibling label
        sibling_label.append('Interp')

    if len(sibling_label) != len(label_parts):
        # We weren't able to find the last part in the marker levels? So
        # there is no preceding sibling.
        return None

    return sibling_label


def label_compare(left, right):
    """ Compare two labels. This sorts labels based on:
            Subpart
            Numerical
            Alphabetical

        "Interp" will be stripped for comparison purposes.
        """
    # Note: Interp labels are special. For comparison purposes, we just
    # remove the '-Interp' from the label. Otherwse we would end up with
    # something like '1234-Interp' being sorted after '1234-1-Interp'.
    if 'Interp' in left:
        left = left.replace('-Interp', '')
    if 'Interp' in right:
        right = right.replace('-Interp', '')

    if 'Subpart' in left and 'Subpart' not in right:
        return -1
    if 'Subpart' in right and 'Subpart' not in left:
        return 1

    return cmp(left, right)


def process_changes(original_xml, original_notice_xml, dry=False):
    """ Process changes given in the notice_xml to modify the
        original_xml. The 'dry' param controls whether this is a
        dry run (True) or to apply the xml changes (False).
        The result is returned as a new XML tree. """

    # Copy the original XML trees for our new tree
    new_xml = deepcopy(original_xml)
    notice_xml = deepcopy(original_notice_xml)

    # Replace the fdsys and preamble with the notice preamble.
    fdsys_elm = new_xml.find('./{eregs}fdsys')
    notice_fdsys_elm = notice_xml.find('./{eregs}fdsys')
    if not dry:
        new_xml.replace(fdsys_elm, notice_fdsys_elm)

    preamble_elm = new_xml.find('./{eregs}preamble')
    notice_preamble_elm = notice_xml.find('./{eregs}preamble')
    if not dry:
        new_xml.replace(preamble_elm, notice_preamble_elm)

    # Get the changes from the notice_xml and iterate over them
    deletions = notice_xml.findall(
        './/{eregs}change[@operation="deleted"]')
    modifications = notice_xml.findall(
        './/{eregs}change[@operation="modified"]')
    additions = notice_xml.findall(
        './/{eregs}change[@operation="added"]')
    movements = notice_xml.findall(
        './/{eregs}change[@operation="moved"]')
    relabelings = notice_xml.findall(
        './/{eregs}change[@operation="changeTarget"]') + \
        notice_xml.findall('.//{eregs}change[@operation="changeLabel"]')


    # Sort them appropriately by label using our custom comparison
    get_label = lambda c: c.get('label')
    deletions = list(reversed(sorted(deletions, key=get_label, cmp=label_compare)))
    modifications = list(reversed(sorted(modifications, key=get_label, cmp=label_compare)))
    additions = list(sorted(additions, key=get_label, cmp=label_compare))
    movements = list(sorted(movements, key=get_label, cmp=label_compare))

    changes = itertools.chain(additions, movements, deletions, modifications, relabelings)
    for change in changes:
        label = change.get('label')
        subpath = change.get('subpath')
        op = change.get('operation')

        logging.info("Applying operation '{}' to {}".format(op, label))
        # For added labels, we need to break up the label and find its
        # parent and its preceding sibling to know where to add it.
        if op == 'added':

            before_label = change.get('before')
            after_label = change.get('after')
            parent_label = change.get('parent')

            label_parts = label.split('-')
            new_elm = change.getchildren()[0]
            new_index = 0

            # First make sure the label doesn't already exist
            matching_elm = new_xml.find('.//*[@label="{}"]'.format(label))
            if matching_elm is not None:
                raise KeyError("Label {} cannot be added because it "
                               "already exists. Was it added in another "
                               "change?".format(label))

            # Get the parent of the added label
            if parent_label is None:
                parent_label = '-'.join(get_parent_label(label_parts))
            parent_elm = new_xml.find('.//*[@label="{}"]'.format(parent_label))

            if parent_elm is None:
                raise TypeError("Label {} cannot be added because its parent "
                                "element '{}' does not exist or is missing a "
                                "'label' attribute".format(label, parent_label))

            # If the parent is a part or subpart, we need to add to the
            # content element.
            if parent_elm.tag in TAGS_WITH_SUBCONTENT:
                parent_elm = parent_elm.find('./{eregs}content')

            # Figure out where we're putting the new element
            # If we're given a before or after label, look
            # for the corresponding elements.
            sibling_label = None
            sibling_elm = None
            # An explicit following-sibling was given
            if before_label is not None:
                sibling_label = before_label
                sibling_elm = new_xml.find('.//*[@label="{}"]'.format(
                    before_label))
                new_index = parent_elm.index(sibling_elm)
            # An explicit preceding-sibling was given
            elif after_label is not None:
                sibling_label = after_label
                sibling_elm = new_xml.find('.//*[@label="{}"]'.format(
                    after_label))
                try:
                    new_index = parent_elm.index(sibling_elm) + 1
                except Exception as e:
                    print("Sibling element '{}' not found".format(sibling_label))
                    raise e
            # If there's an explicit parent but no siblings, insert at
            # the beginning of the parent.
            elif change.get('parent') is not None:
                new_index = len(parent_elm.getchildren())
            else:
                # Guess the preceding sibling
                sibling_label_parts = get_sibling_label(label_parts)
                if sibling_label_parts is not None:
                    sibling_label = '-'.join(sibling_label_parts)
                    sibling_elm = new_xml.find(
                        './/*[@label="{}"]'.format(sibling_label))
                    try:
                        new_index = parent_elm.index(sibling_elm) + 1
                    except TypeError:
                        new_index = len(parent_elm.getchildren())

                # Give up on a particular location and append to the end
                # of the parent.
                else:
                    new_index = len(parent_elm.getchildren())

            # Insert the new xml!
            if not dry:
                parent_elm.insert(new_index, new_elm)


        # Handle existing elements
        if op in ('moved', 'modified', 'deleted'):
            # Find a match to the given label and subpath (optional)
            # NOTE: If subpath isn't a single sub-element of a labelled node,
            # inserting the namespace into findstr between label and subpath
            # will PROBABLY be the problem you're looking for
            if subpath is not None:
                findstr = './/*[@label="{}"]/{}{}'.format(label, "{eregs}", subpath)
                matching_elm = new_xml.find(findstr)
                logging.debug("Performing {} operation on '{}'".format(op, findstr))

                if matching_elm is None:
                    logging.debug("Finding str: {}".format(repr(findstr)))
                    raise KeyError("Unable to find element '{}' to be {}".format(findstr, op))
            else:
                matching_elm = new_xml.find('.//*[@label="{}"]'.format(label))
                logging.debug("Performing {} operation on '{}'".format(op, label))
                if matching_elm is None:
                    raise KeyError("Unable to find label {} to be {}".format(label, op))

            match_parent = matching_elm.getparent()

            # For moved labels, we need to find the new parent label
            if op == 'moved':
                parent_label = change.get('parent')
                before_label = change.get('before')
                after_label = change.get('after')

                # Find the new parent element
                parent_elm = new_xml.find('.//*[@label="{}"]'.format(parent_label))
                if parent_elm is None:
                    raise ValueError("'parent' attribute is required "
                                     "for 'moved' operation on "
                                     "{}".format(label))

                # If the parent is a part or subpart, we need to add to the
                # content element, unless this is an item found by subpath with no content
                if parent_elm.tag in TAGS_WITH_SUBCONTENT and subpath is None:
                    parent_elm = parent_elm.find('./{eregs}content')

                # Figure out where we're putting the element when we
                # move it. If we're given a before or after label, look
                # for the corresponding elements.
                new_index = 0
                before_elm = new_xml.find('.//*[@label="{}"]'.format(
                    before_label))
                after_elm = new_xml.find('.//*[@label="{}"]'.format(
                    after_label))
                if before_elm is not None:
                    new_index = parent_elm.index(before_elm)
                elif after_elm is not None:
                    new_index = parent_elm.index(after_elm) + 1
                else:
                    # Otherwise, just append it to the end of the parent.
                    new_index = len(parent_elm.getchildren())

                # Move it!
                if not dry:
                    parent_elm.insert(new_index, matching_elm)

            # For modified labels, just find the node and replace it.
            if op == 'modified':
                if len(change.getchildren()) == 0:
                    raise ValueError("Tried to modify {}, but no "
                                     "replacement given".format(label))

                if not dry:
                    new_elm = change.getchildren()[0]
                    match_parent.replace(matching_elm, new_elm)

            # For deleted labels, find the node and remove it.
            if op == 'deleted':

                if not dry:

                    # Remove the element itself
                    match_parent.remove(matching_elm)

        if op == 'changeTarget':

            old_target = change.get('oldTarget')
            new_target = change.get('newTarget')
            target_text = change.text

            if old_target is None or new_target is None:
                raise ValueError('Need to know both the old target and '
                                 'the new target to relabel a reference!')

            references = new_xml.findall('.//{{eregs}}ref[@target="{}"]'.format(old_target))
            for ref in references:
                if target_text is None or ref.text.lower() == target_text.lower():
                    ref.set('target', new_target)

        if op == 'changeLabel':

            new_label = change.get('newLabel')
            if new_label is None:
                raise ValueError('Need to know the new label to assign to the target')
            matching_elm = new_xml.find('.//*[@label="{}"]'.format(label))
            logging.debug("Performing {} operation on '{}'".format(op, label))
            if matching_elm is None:
                raise KeyError("Unable to find label {} to be {}".format(label, op))
            matching_elm.set('label', new_label)

    return new_xml


def process_analysis(regulation_xml, notice_xml, dry=False):
    """ Given a notice tree and a regulation xml tree, add any analysis
        in the notice to the regulation. If analysis for the same target
        already exists, it will be replaced. """

    notice_analysis = notice_xml.find('.//{eregs}analysis')

    # If there is no notice analysis, we have nothing to do here.
    if notice_analysis is None:
        # print("No analysis found in notice.")
        return regulation_xml

    existing_analysis = regulation_xml.find('.//{eregs}analysis')

    # If there's no existing analysis, but the notice contains
    # analysis, just copy from the notice wholesale.
    if existing_analysis is None and notice_analysis is not None:
        regulation_xml.append(notice_analysis)
        return regulation_xml

    # Go through and add the new analysis
    for new_section in notice_analysis.getchildren():
        existing_analysis.append(new_section)

    return regulation_xml


def rectify_analysis(notice_xml, dry=False):
    """
    Parses through the analysis section and fixes common problems:
    - analysisSection with only a title: adds an empty analysisParagraph
    """

    new_xml = deepcopy(notice_xml)
    notice_analysis = new_xml.find('.//{eregs}analysis')

    # If there is no notice analysis, we have nothing to do here.
    if notice_analysis is None:
        return

    # Iterate through the tree and find any problem areas
    for toplevelsection in notice_analysis.iterchildren():
        sections = toplevelsection.findall('.//{eregs}analysisSection')
        
        # Determine whether this section has non-title children
        for section in sections:
            title = section.find('{eregs}title')
            subsections = len(section.findall('{eregs}analysisSection'))
            subparas = len(section.findall('{eregs}analysisParagraph'))

            # Find analysisSection nodes that don't fit the schema because
            # they have no child analysisSection or analysisParagraph.
            if subsections + subparas == 0:
                print("Found no subsections or subparas in {0}".format(title))

                # Insert an empty analysisParagraph node so the schema validates.
                if not dry:
                    etree.SubElement(section, "{eregs}analysisParagraph")

    return new_xml


def generate_diff(left_xml, right_xml):
    """ Given two full RegML trees, generate a dictionary of changes
        between the two in the style of regulations-parser.
        This wraps regulatons-parser's changes_between() function. """
    left_tree = build_reg_tree(left_xml)
    right_tree = build_reg_tree(right_xml)
    diff = dict(changes_between(FrozenNode.from_node(left_tree),
                                FrozenNode.from_node(right_tree)))
    return diff
