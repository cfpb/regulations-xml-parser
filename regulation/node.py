# -*- coding: utf-8 -*-

from collections import OrderedDict
from termcolor import colored
import re

class RegNode:

    def __init__(self, **kwargs):

        self.label = []
        self.marker = None
        self.children = []
        self.text = ''
        self.title = ''
        self.node_type = ''
        self.hash = ''

        self.mixed_text = []

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

        # if self.mixed_text != []:
        #     node_dict['mixed_text'] = self.mixed_text

        return node_dict

    def __repr__(self):

        return str(self.to_json())

    @staticmethod
    def merkle_hash(node):
        # Merkle hash implementation
        if node.children == []:
            return hash('-'.join(node.label) + node.node_type + node.text)
        else:
            child_hashes = ''
            for child in node.children:
                child_hash = str(RegNode.merkle_hash(child))
                child_hashes += child_hash
            return hash(child_hashes)

    def __hash__(self):
        self.hash = RegNode.merkle_hash(self)
        return self.hash


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