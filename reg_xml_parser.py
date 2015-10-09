#!/usr/bin/env python

__author__ = 'vinokurovy'

import argparse
import sys
import os
import json

from lxml import etree
from pprint import pprint

from regulation.tree import build_reg_tree


def parser_driver(regulation_file, notice_doc_numbers=[]):

    with open(regulation_file, 'r') as f:
        reg_xml = f.read()
    xml_tree = etree.fromstring(reg_xml)
    reg_tree = build_reg_tree(xml_tree)

    reg_tree.include_children = True
    reg_json = reg_tree.to_json()

    json_file = regulation_file.replace('xml', 'json')
    json.dump(reg_json, open(json_file, 'w'), indent=4, separators=(',', ': '))


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--operation', dest='operation', action='store')
    parser.add_argument('regulation-file', nargs='?')
    parser.add_argument('notice-doc-numbers', nargs='*')

    args = vars(parser.parse_args())

    if args['regulation-file'] is not None:
        parser_driver(args['regulation-file'])