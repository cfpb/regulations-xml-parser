# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from copy import deepcopy
import itertools
import logging

# Import regparser here with the eventual goal of breaking off the parts
# we're using in the RegML parser into a library both can share.
from regparser.tree.paragraph import p_levels
from regparser.tree.struct import FrozenNode
from regparser.diff.tree import changes_between

from regulation.tree import build_reg_tree


logger = logging.getLogger(__name__)


def get_parent_label(label_parts):
    """ Determine the parent label for the given label part list. """
    parent_label = None

    # It can't have a parent if it's only one part
    if len(label_parts) <= 1:
        return parent_label

    # Not an interpretation label. This is easy.
    parent_label = label_parts[0:-1]

    if label_parts[-1] == 'Interp':
        # It's the whole interp for the label. Get the parent and
        # add Interp again.
        parent_label = get_parent_label(parent_label)
        parent_label.append('Interp')

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
        # We weren't able to find the last part in the marker levels?
        raise IndexError("Unable to locate sibling for '{}'".format(
            last_part))

    return sibling_label


def process_changes(original_xml, notice_xml, dry=False):
    """ Process changes given in the notice xml to modify the
        original_xml. The result is returned as a new XML tree. """

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

    # Sort them appropriately by label
    get_label = lambda c: c.get('label')
    deletions = list(reversed(sorted(deletions, key=get_label)))
    modifications = list(reversed(sorted(modifications, key=get_label)))
    additions = list(sorted(additions, key=get_label))

    changes = itertools.chain(deletions, modifications, additions)
    for change in changes:
        label = change.get('label')
        op = change.get('operation')

        logging.info("Applying {} to {}".format(op, label))

        # For added labels, we need to break up the label and find its
        # parent and its preceding sibling to know where to add it.
        if op == 'added':
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
            parent_label = '-'.join(get_parent_label(label_parts))
            parent_elm = new_xml.find('.//*[@label="{}"]'.format(parent_label))

            # Get the sibling of the added label
            sibling_label_parts = get_sibling_label(label_parts)
            if sibling_label_parts is not None:
                sibling_label = '-'.join(sibling_label_parts)
                sibling_elm = new_xml.find(
                    './/*[@label="{}"]'.format(sibling_label))

                # Figure out where we're inserting this element
                new_index = parent_elm.index(sibling_elm) + 1

            # Insert it!
            if not dry:
                parent_elm.insert(new_index, new_elm)

        if op in ('modified', 'deleted'):
            # Find a match to the given label
            matching_elm = new_xml.find('.//*[@label="{}"]'.format(label))
            if matching_elm is None:
                raise KeyError("Unable to find label {} {} in "
                               "notice.".format(label, op))

            match_parent = matching_elm.getparent()

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
