# -*- coding: utf-8 -*-

from collections import OrderedDict
from termcolor import colored

import re
import json
import hashlib

class RegNode:

    def __init__(self, **kwargs):

        self.label = []
        self.marker = None
        self.children = []
        self.text = ''
        self.title = ''
        self.node_type = ''
        self.hash = None
        self.depth = 0

        self.mixed_text = []
        self.source_xml = ''

        if 'include_children' in kwargs:
            if not (kwargs['include_children'] is True or
                    kwargs['include_children'] is False):
                raise ValueError('include_children must be True or False!')
            self.include_children = kwargs['include_children']
        else:
            self.include_children = False

    def to_json(self):

        node_dict = OrderedDict()

        if self.include_children:
            node_dict['children'] = [node.to_json()
                                     for node in self.children]

        node_dict['label'] = self.label
        node_dict['node_type'] = self.node_type
        node_dict['text'] = self.text
        if self.title and self.title != '':
            node_dict['title'] = self.title
        if self.marker:
            node_dict['marker'] = self.marker

        if self.mixed_text != []:
            pass
            #node_dict['mixed_text'] = self.mixed_text

        return node_dict

    def __repr__(self):

        return json.dumps(self.to_json(), indent=4)

    def __str__(self):
        return self.__repr__()

    def __eq__(self, other):
        if self.__class__ == other.__class__ and self.interior_hash == other.interior_hash:
            return True
        else:
            return False

    @staticmethod
    def merkle_hash(node):
        # Merkle hash implementation
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
        return hash(self.node_type + self.text + self.source_xml)

    @property
    def string_label(self):
        return '-'.join(self.label)

    def find_node(self, func):
        """
        Find all nodes in the subtree of self that match the specified predicate.
        :param function: predicate to match
        :return: a flat list of the nodes matching that predicate
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
        :return:
        """

        #import pdb
        #pdb.set_trace()

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
        :return:
        """

        import pdb
        #pdb.set_trace()

        if self.children == []:
            return [self.string_label]
        else:
            child_labels = []
            for child in self.children:
                child_labels.extend(child.labels())
            return [self.string_label] + child_labels

    def height(self):
        """
        Calculate the height of the tree starting from the root and down to the lowest leaf/
        :return: The tree height
        """
        if len(self.children) == 0:
            return 1
        else:
            return 1 + max([child.height() for child in self.children])


def xml_node_text(node, include_children=True):

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

def find_all_occurrences(source, target):

    positions = []
    remainder = source
    start = 0
    while remainder != []:
        pos = remainder.find(target)
        if pos != -1:
            positions.append(pos + start)
            pivot = pos + len(target)
            start += len(remainder[:pivot])
            remainder = remainder[pivot:]
        else:
            remainder = []

    return positions


def interpolate_string(text, offsets, values, colorize=False):
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