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
    

def process_changes(original_xml, notice_xml, dry=False):
    """ Process changes given in the notice_xml to modify the
        original_xml. The 'dry' param controls whether this is a
        dry run (True) or to apply the xml changes (False).
        The result is returned as a new XML tree. """

    # Copy the original XML for our new tree
    new_xml = deepcopy(original_xml)

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

    # Sort them appropriately by label using our custom comparison
    get_label = lambda c: c.get('label')
    deletions = list(reversed(sorted(deletions, key=get_label, cmp=label_compare)))
    modifications = list(reversed(sorted(modifications, key=get_label, cmp=label_compare)))
    additions = list(sorted(additions, key=get_label, cmp=label_compare))
    movements = list(sorted(movements, key=get_label, cmp=label_compare))

    changes = itertools.chain(additions, movements, modifications, deletions)
    for change in changes:
        label = change.get('label')
        subpath = change.get('subpath')
        op = change.get('operation')

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
                new_index = parent_elm.index(sibling_elm) + 1
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
                findstr = str('.//*[@label="{}"]/{}{}'.format(label, "{eregs}", subpath))
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
