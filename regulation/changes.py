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

    # Find the tables of contents in the original xml
    # for handy reference later when updating TOC entries
    # tocs = new_xml.findall('.//{eregs}tableOfContents')
    tocs = find_tocs(new_xml)
    logging.debug("Found {} TOCs in document".format(len(tocs)))

    # Sort them appropriately by label
    # Note: Interp labels are special. For comparison purposes, we just
    # remove the '-Interp' from the label. Otherwse we would end up with
    # something like '1234-Interp' being sorted after '1234-1-Interp'.
    get_label = lambda c: c.get('label') \
                          if 'Interp' not in c.get('label') \
                          else c.get('label').replace('-Interp', '')
    deletions = list(reversed(sorted(deletions, key=get_label)))
    modifications = list(reversed(sorted(modifications, key=get_label)))
    additions = list(sorted(additions, key=get_label))

    changes = itertools.chain(deletions, modifications, additions)
    for change in changes:
        label = change.get('label')
        op = change.get('operation')

        logging.info("Applying operation '{}' to {}".format(op, label))

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
            else:
                # If the sibling label is none, just append it to the
                # end of the parent.
                new_index = len(parent_elm.getchildren())

            # TODO: Perform TOC updates if needed
            # - Determine whether the sibling's label appears in TOC(s)
            # - If so, after the sibling's tocSecEntry, create a tocSecEntry for the new addition
            # - Insert the new tocSecEntry after the sibling's tocSecEntry

            # Insert the new xml!
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

                # Look for whether a modified label exists in a TOC and if so, update the TOC name
                # If the label exists as a tocSecEntry target, update the sectionSubject

                # In a modified <change>, the <section> tag has a label and a sectionNum
                # - Check if the label exists as a tocSecEntry target
                # - Replace the tocSecEntry's child <sectionNum> content with sectionNum specified
                # - Replace the tocSecEntry's child <sectionSubject> content with changed <subject> content
                # Note: This label may exist as a target in multiple TOCs - all need to be updated
                # sections = [el for el in change.iterchildren() if el.tag == "{eregs}section"]
                sections = change.findall('{eregs}section')

                logging.debug("Found {} sections in this change".format(len(sections)))
                
                for section in sections:
                    toc_label = section.get('label')
                    toc_secnum = section.get('sectionNum')
                    toc_subject = section.find('{eregs}subject').text

                    toc_updates = multi_find_toc_entry(tocs, toc_label)

                    logging.debug("Found {} TOC entries for section {} ('{}'): '{}'".format(len(toc_updates),
                                                                                            toc_secnum,
                                                                                            toc_label,
                                                                                            toc_subject))

                    if not dry:
                        changed = 0
                        for toc_entry in toc_updates:
                            changed += update_toc_entry(toc_entry, toc_secnum, toc_subject)
                        logging.info("Made {} updates to TOC entries for section {} ('{}')".format(changed,
                                                                                            toc_secnum,
                                                                                            toc_label))

                if not dry:
                    new_elm = change.getchildren()[0]
                    match_parent.replace(matching_elm, new_elm)

            # For deleted labels, find the node and remove it.
            if op == 'deleted':
                # Look for whether a deleted label exists in TOCs and if so, delete the TOC entry
                # If the label exists as a tocSecEntry target, delete the TOC entry and its children
                # Note: This label may exist as a target in multiple TOCs - all need to be updated

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


def find_tocs(source_xml):
    """
    Finds <tableOfContents> nodes inside the source_xml and returns a list of them
    """
    return source_xml.findall('.//{eregs}tableOfContents')

def get_toc_entries(toc_root):
    """
    Retrieves a list of Table of Contents section entries (<tocSecEntry>) for the specified TOC
    """
    # Get a list of toc section entries
    sec_entries = [el for el in toc_root.iterchildren()]

    # Sort list by toc section targets - should already be sorted by target but just to be sure
    get_target = lambda c: c.get('target')
    sec_entries = list(reversed(sorted(sec_entries, key=get_target)))

    return sec_entries


def find_toc_entry(toc_root, toc_target):
    """
    Finds a Table of Contents entry by target inside the given <tableOfContents> element.

    Returns the found tocSecEntry node or returns None.
    """
    # Get all secEntries
    sec_entries = get_toc_entries(toc_root)

    # Look for matching target inside
    for sec in sec_entries:
        if sec.get('target') == toc_target:
            return sec

    # raise KeyError("Unable to find TOC entry with target '{}'.".format(toc_target))
    return None


def multi_find_toc_entry(tocs, toc_target):
    """
    Finds a <tocSecEntry> by target in multiple TOCs. 
    Returns a list of all found entries or an empty list if no entries are found.
    """
    found_entries = []

    for toc in tocs:
        found = find_toc_entry(toc, toc_target)
        if found is not None:
            found_entries.append(found)

    return found_entries


def update_toc_entry(toc_entry, new_secnum, new_subject):
    """
    Updates the specified tocSecEntry with the given section number and subject.
    Returns whether anything changed inside the toc_entry
    """

    old_num = toc_entry.find('{eregs}sectionNum').text
    old_subject = toc_entry.find('{eregs}sectionSubject').text

    changed = False

    # If num changes, update it
    if int(old_num) != int(new_secnum):
        changed = True
        # TODO: Actually update this
        toc_entry.find('{eregs}sectionNum').text = new_secnum
        logging.debug("Updating TOC section number: {} -> {}".format(old_num, new_secnum))

    # If subject changes, update it
    if old_subject != new_subject:
        changed = True
        # TODO: Actually update this
        toc_entry.find('{eregs}sectionSubject').text = new_subject
        logging.debug("Updating TOC contents:\nOld: '{}'\nNew: '{}'".format(old_subject, new_subject))

    if not changed:
        logging.debug("No TOC updates needed")
    
    return changed

