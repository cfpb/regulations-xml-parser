#!/usr/bin/env python

import argparse
import sys
import os
import json

from lxml import etree

from regulation.tree import (build_analysis,
                             build_external_citations_layer, 
                             build_formatting_layer,
                             build_graphics_layer, 
                             build_internal_citations_layer,
                             build_interp_layer, 
                             build_keyterm_layer, 
                             build_meta_layer,
                             build_notice, 
                             build_paragraph_marker_layer, 
                             build_reg_tree,
                             build_terms_layer, 
                             build_toc_layer)
from regulation.verification import EregsValidator

import settings

reload(sys)
sys.setdefaultencoding('UTF8')


def write_layer(layer_object, reg_number, notice, layer_type):

    layer_path = os.path.join(settings.JSON_ROOT, layer_type, reg_number)
    if not os.path.exists(layer_path):
        os.mkdir(layer_path)
    layer_file = os.path.join(layer_path, notice)
    json.dump(layer_object, open(layer_file, 'w'), indent=4, 
              separators=(',', ':'))


def parser_driver(regulation_file, notice_doc_numbers=[]):
    with open(regulation_file, 'r') as f:
        reg_xml = f.read()
    xml_tree = etree.fromstring(reg_xml)

    reg_tree = build_reg_tree(xml_tree)
    reg_number = reg_tree.label[0]

    paragraph_markers = build_paragraph_marker_layer(xml_tree)
    internal_citations = build_internal_citations_layer(xml_tree)
    external_citations = build_external_citations_layer(xml_tree)
    terms = build_terms_layer(xml_tree)
    meta = build_meta_layer(xml_tree)
    toc = build_toc_layer(xml_tree)
    keyterms = build_keyterm_layer(xml_tree)
    graphics = build_graphics_layer(xml_tree)
    formatting = build_formatting_layer(xml_tree)
    interps = build_interp_layer(xml_tree)
    analysis = build_analysis(xml_tree)
    notice = build_notice(xml_tree)

    # validate relative to schema
    validator = EregsValidator(settings.XSD_FILE)
    validator.validate_reg(xml_tree)

    # if the validator had problems then we should report them and bail out
    if not validator.is_valid:
        for event in validator.events:
            print str(event)
        sys.exit(0)
    else:
        validator.validate_terms(xml_tree, terms)
        validator.validate_internal_cites(xml_tree, internal_citations)
        for event in validator.events:
            print str(event)

    reg_tree.include_children = True
    reg_json = reg_tree.to_json()

    notice = notice_doc_numbers[0]

    write_layer(reg_json, reg_number, notice, 'regulation')
    write_layer(meta, reg_number, notice, 'layer/meta')
    write_layer(paragraph_markers, reg_number, notice, 
                'layer/paragraph-markers')
    write_layer(internal_citations, reg_number, notice, 
                'layer/internal-citations')
    write_layer(external_citations, reg_number, notice, 
                'layer/external-citations')
    write_layer(terms, reg_number, notice, 'layer/terms')
    write_layer(toc, reg_number, notice, 'layer/toc')
    write_layer(keyterms, reg_number, notice, 'layer/keyterms')
    write_layer(graphics, reg_number, notice, 'layer/graphics')
    write_layer(formatting, reg_number, notice, 'layer/formatting')
    write_layer(interps, reg_number, notice, 'layer/interpretations')
    write_layer(analysis, reg_number, notice, 'layer/analysis')
    write_layer(notice, reg_number, notice, 'notice')

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--operation', dest='operation', action='store')
    parser.add_argument('regulation-file', nargs='?')
    parser.add_argument('notice-doc-numbers', nargs='*')

    args = vars(parser.parse_args())

    if args['regulation-file'] is not None:
        parser_driver(args['regulation-file'], args['notice-doc-numbers'])
