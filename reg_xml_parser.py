#!/usr/bin/env python

__author__ = 'vinokurovy'

import argparse
import sys
import os
import json
import codecs

from lxml import etree
from pprint import pprint

from regulation.tree import *

reload(sys)
sys.setdefaultencoding('UTF8')

def parser_driver(regulation_file, notice_doc_numbers=[]):

    #f = codecs.open(regulation_file, encoding='utf-8')
    with open(regulation_file, 'r') as f:
        reg_xml = f.read()
    xml_tree = etree.fromstring(reg_xml)
    reg_tree = build_reg_tree(xml_tree)
    paragraph_markers = build_paragraph_marker_layer(xml_tree)
    internal_citations = build_internal_citations_layer(xml_tree)
    external_citations = build_external_citations_layer(xml_tree)
    terms = build_terms_layer(xml_tree)

    reg_tree.include_children = True
    reg_json = reg_tree.to_json()

    reg_json_file = regulation_file.replace('xml', 'json')
    json.dump(reg_json, open(reg_json_file, 'w'), indent=4, separators=(',', ': '))

    layer_path = os.path.split(regulation_file)
    file_name = layer_path[-1].replace('xml', 'json')
    layer_path = os.path.split(layer_path[0])
    version = layer_path[-1]
    layer_path = os.path.split(layer_path[0])[0]

    layer_file = os.path.join(layer_path, 'layer', 'paragraph-markers', version, file_name)
    json.dump(paragraph_markers, open(layer_file, 'w'), indent=4, separators=(',', ': '))
    print layer_file

    layer_file = os.path.join(layer_path, 'layer', 'internal-citations', version, file_name)
    json.dump(internal_citations, open(layer_file, 'w'), indent=4, separators=(',', ': '))
    print layer_file

    layer_file = os.path.join(layer_path, 'layer', 'external-citations', version, file_name)
    json.dump(external_citations, open(layer_file, 'w'), indent=4, separators=(',', ': '))
    print layer_file

    layer_file = os.path.join(layer_path, 'layer', 'terms', version, file_name)
    json.dump(terms, open(layer_file, 'w'), indent=4, separators=(',', ': '))
    print layer_file

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--operation', dest='operation', action='store')
    parser.add_argument('regulation-file', nargs='?')
    parser.add_argument('notice-doc-numbers', nargs='*')

    args = vars(parser.parse_args())

    if args['regulation-file'] is not None:
        parser_driver(args['regulation-file'])