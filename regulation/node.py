__author__ = 'vinokurovy'

import json
import re

from collections import OrderedDict

class RegNode:

    def __init__(self, **kwargs):

        self.label = []
        self.marker = None
        self.children = []
        self.text = ''
        self.title = ''
        self.node_type = ''

        if 'include_children' in kwargs:
            if not (kwargs['include_children'] == True or kwargs['include_children'] == False):
                raise ValueError('include_children must be True or False!')
            self.include_children = kwargs['include_children']
        else:
            self.include_children = False

    def to_json(self):

        node_dict = OrderedDict()

        if self.include_children:
            node_dict['children'] = [node.to_json() for node in self.children]

        node_dict['label'] = self.label
        node_dict['node_type'] = self.node_type
        node_dict['text'] = self.text
        if self.title and self.title != '':
            node_dict['title'] = self.title
        if self.marker:
            node_dict['marker'] = self.marker

        return node_dict

    def __repr__(self):

        return str(self.to_json())


def xml_node_text(node):

    if node.text:
        node_text = node.text
    else:
        node_text = ''

    for child in node.getchildren():
        if child.text:
            node_text += child.text
        if child.tail:
            node_text += child.tail

    return node_text