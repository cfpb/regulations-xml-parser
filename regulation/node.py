# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from collections import OrderedDict
from termcolor import colored

import re
import json
import hashlib

"""
Created on Jan 1, 2016
@author: Jerry Vinokurov, Will Barton
"""


class RegNode:
    """
    The RegNode class represents a regular text node in a regulation.
    It provides for some convenience functions for manipulating the
    tree hierarchy if necessary.

    Keyword arguments:
        `include_children` (**bool**): whether or not to include children when generating JSON
    """
    def __init__(self, **kwargs):
        """
        The initializer for the RegNode class.

        Args:
            \*\*kwargs: keyword arguments

        Keyword arguments:
            include_children (bool): whether or not to include children when generating JSON
        """
        self.label = []
        self.marker = None
        self.children = []
        self.text = ''
        self.title = ''
        self.node_type = ''
        self.hash = None
        self.depth = 0

        self.mixed_text = []
        self.source_xml = None

        if 'include_children' in kwargs:
            if not (kwargs['include_children'] is True or
                    kwargs['include_children'] is False):
                raise ValueError('include_children must be True or False!')
            self.include_children = kwargs['include_children']
        else:
            self.include_children = False

    def to_json(self):
        """
        Convert yourself, and possibly all your children, into JSON.

        Returns:
            :class:`collections.OrderedDict`: A dict representing the node, suitable for
            direct use wherever JSON is expected.
        """
        node_dict = OrderedDict()

        if self.include_children:
            node_dict['children'] = [node.to_json()
                                     for node in self.children]

        node_dict['label'] = self.label
        node_dict['node_type'] = self.node_type
        node_dict['text'] = self.text
        if self.title and self.title != '':
            node_dict['title'] = self.title
        if self.marker is not None:
            node_dict['marker'] = self.marker

        if self.mixed_text != []:
            pass
            #node_dict['mixed_text'] = self.mixed_text

        return node_dict

    def __repr__(self):
        return json.dumps(self.to_json(), indent=4)

    def __str__(self):
        return self.__repr__()

    def __cmp__(self, other):
        return cmp(repr(self), repr(other))

    def label_id(self):
        return '-'.join(self.label)

    def __eq__(self, other):
        if self.__class__ == other.__class__ and self.interior_hash == other.interior_hash:
            return True
        else:
            return False

    @staticmethod
    def merkle_hash(node):
        """
        An implementation of Merkle hashes for determining whether a node has changed.
        Currently unused.

        :param node: the node to hash.
        :type node: :class:`regulation.node.RegNode`

        :return: an integer representing the hash of the node.
        :rtype: :class:`int`
        """

        if node.children == []:
            #return hash('-'.join(node.label) + node.node_type + node.text + node.source_xml)
            return hash(node.node_type + node.text + node.source_xml)
        else:
            child_hashes = ''
            for child in node.children:
                child_hash = str(RegNode.merkle_hash(child))
                child_hashes += child_hash
            return hash(child_hashes)

    def __hash__(self):
        if self.hash is None:
            self.hash = RegNode.merkle_hash(self)
        return self.hash

    @property
    def interior_hash(self):
        """
        An interior hash that only takes into account the node type, its text, and the XML it is based on.

        :param: None

        :return: an integer representing the hash of the node's fields.
        :rtype: :class:`int`
        """
        return hash((self.node_type or '') + (self.text or '') + (self.source_xml or ''))

    @property
    def string_label(self):
        """
        The label of the node as a single string.

        :param: None

        :return: a string representing the node label.
        :rtype: :class:`str`
        """
        return '-'.join(self.label)

    def find_node(self, func):
        """
        Find all nodes in the subtree of self that match the specified predicate.

        :param func: predicate to match.
        :type func: :class:`function`

        :return: a flat list of the RegNodes matching that predicate
        :rtype: :class:`list` of :class:`regulation.node.RegNode`
         """
        matches = [child for child in self.children if func(child)]

        submatches = []
        for child in self.children:
            submatches.extend(child.find_node(func))
        matches.extend(submatches)

        return matches

    def flatten(self):
        """
        Return this node and all its children in a flat list

        :param: None

        :return: a flat list of RegNodes.
        :rtype: :class:`list` of :class:`regulation.node.RegNode`:
        """

        if self.children == []:
            new_node = RegNode()
            new_node.node_type = self.node_type
            new_node.label = self.label
            new_node.text = self.text
            new_node.mixed_text = self.mixed_text
            new_node.source_xml = self.source_xml
            return [new_node]
        else:
            new_node = RegNode()
            new_node.node_type = self.node_type
            new_node.label = self.label
            new_node.text = self.text
            new_node.mixed_text = self.mixed_text
            new_node.source_xml = self.source_xml
            flatten_children = [new_node]
            for child in self.children:
                flatten_children.extend(child.flatten())
            return flatten_children

    def labels(self):
        """
        Return the list of all labels used in the tree

        :param: None

        :return: a list of strings that are labels used in the tree.
        :rtype: :class:`list` of :class:`str`
        """

        if self.children == []:
            return [self.string_label]
        else:
            child_labels = []
            for child in self.children:
                child_labels.extend(child.labels())
            return [self.string_label] + child_labels

    def height(self):
        """
        Calculate the height of the tree starting from the root and down to the lowest leaf.

        :param: None.
        :return: the tree height.
        :rtype: :class:`int`
        """
        if len(self.children) == 0:
            return 1
        else:
            return 1 + max([child.height() for child in self.children])


def xml_node_text(node, include_children=True):
    """
    Extract the raw text from an XML element.

    :param node: the XML element, usually ``<content>``.
    :type node: :class:`etree.Element`
    :param include_children: whether or not to get the text of the children as well.
    :type include_children: :class:`bool` - optional, default = True

    :return: a string of the text of the node without any markup.
    :rtype: :class:`str`
    """

    if node.text:
        node_text = node.text
    else:
        node_text = ''

    if include_children:
        for child in node.getchildren():
            if child.text:
                node_text += child.text
            if child.tail:
                node_text += child.tail

    else:
        for child in node.getchildren():
            if child.tail:
                node_text += child.tail.strip()

    return node_text


def xml_mixed_text(node):

    text_fragments = []
    if node.text and node.text.strip() != '':
        text_fragments.append(node.text)

    for child in node.getchildren():
        if child.text and child.text.strip() != '':
            node_dict = {'tag': child.tag.replace('{eregs}', '')}
            for k, v in child.attrib.items():
                node_dict[k] = v
            node_dict['text'] = child.text.strip()
            text_fragments.append(node_dict)
        if child.tail and child.tail.strip() != '':
            text_fragments.append(child.tail)

    return text_fragments


def xml_node_hash(node):

    hasher = hashlib.sha256()
    hasher.update(node.tag)
    if node.tag == '{eregs}paragraph' or node.tag == '{eregs}interpParagraph':
        title = node.find('{eregs}title')
        if title is not None:
            hasher.update(title.text)
        content = node.find('{eregs}content')
        if content is not None:
            defs = content.findall('{eregs}def')
            refs = content.findall('{eregs}ref')
            for defn in defs:
                hasher.update(defn.get('term'))
                hasher.update(defn.text)
            for ref in refs:
                hasher.update(ref.get('target'))
                hasher.update(ref.get('reftype'))
                hasher.update(ref.text)

    return hasher.hexdigest()


def xml_node_equality(node1, node2):

    if node1.__class__ == node2.__class__ and xml_node_hash(node1) == xml_node_hash(node2):
        return True
    else:
        return False


def find_all_occurrences(source, target, boundary=True):
    """
    Find all occurrences of `target` in `source`

    :param source: the source string to search within.
    :type source: :class:`str`
    :param target: the target string to search for.
    :type target: :class:`str`:

    :return: list of positions at which `source` occurs in `target`.
    :rtype: :class:`list` of :class:`int`
    """
    positions = []
    if boundary:
        results = re.finditer(r"\b" + re.escape(target) + r"\b", source)
    else:
        results = re.finditer(r"\b" + re.escape(target), source)
    for match in results:
        positions.append(match.start())
    return positions


def interpolate_string(text, offsets, values, colorize=False):
    """
    Interpolate the `values` into the `text` at a given `offset`.


    :param text: the text string into which to interpolate the `values`.
    :type text: :class:`str`
    :param offsets: a list of 2-tuples of integers representing the start and end of the interpolated text.
    :type offsets: :class:`tuple` of :class:`int`
    :param values: the list of values to be interpolated into the text.
    :type values: :class:`list` of :class:`str`
    :param colorize: flag to return a "colorized" version of the text, useful for highlighting.
    :type colorize: :class:`bool`- optional, default = False

    :return: the `text` with each `value` interpolated at the specified `offsets`.
    :rtype: :class:`str`
    """
    result = ''
    current_pos = 0
    for i, offset in enumerate(offsets):
        start = offset[0]
        end = offset[1]
        if colorize:
            fragment = colored(text[current_pos:start], 'green')
        else:
            fragment = text[current_pos:start]
        current_pos = end
        if colorize:
            result = result + fragment + colored(values[i], 'red')
        else:
            result = result + fragment + values[i]
    if colorize:
        result = result + colored(text[current_pos:], 'green')
    else:
        result = result + text[current_pos:]
    return result


def enclosed_in_tag(source_text, tag, loc):
    """
    Determine whether within the `source_text`, the element present at `loc` is enclosed within the XML `tag`.

    :param source_text: a string that possibly contains some XML markup.
    :type source_text: :class:`str`
    :param tag: a string specifying an XML tag.
    :type tag: :class:`str`
    :param loc: the location to test for enclosure.
    :type loc: :class:`int`

    :return: a boolean indicating whether `loc` is enclosed in the specified `tag`.
    :rtype: :class:`bool`

    Example:
    ::
        source_text = '<foo>bar</foo>'
        tag = 'foo'
        loc = 6
        enclosed_in_tag(source_text, tag, loc)
        True
    """
    trailing_text = source_text[loc:]
    close_tag = '</{}>'.format(tag)
    first_open_tag = re.search('<[^\/].*?>', trailing_text)
    first_closed_tag = re.search('<\/.*?>', trailing_text)
    if not first_closed_tag:
        return False
    else:
        if first_open_tag is not None and first_open_tag.start() < first_closed_tag.start():
            return False
        elif first_closed_tag.group(0) == close_tag:
            return True
        else:
            return False
