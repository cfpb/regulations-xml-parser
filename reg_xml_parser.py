#!/usr/bin/env python
from __future__ import print_function

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

from regulation.validation import EregsValidator
from regulation.diff import *
from itertools import combinations
from utils.graph import build_graph

import settings

if (sys.version_info < (3, 0)):
    reload(sys)  # noqa
    sys.setdefaultencoding('UTF8')


def diff_driver(regulation_files):

    pairs = combinations(regulation_files, 2)
    for pair in pairs:
        with open(pair[0], 'r') as f:
            xml_tree1 = etree.fromstring(f.read())

        with open(pair[1], 'r') as f:
            xml_tree2 = etree.fromstring(f.read())

        reg_tree1 = build_reg_tree(xml_tree1)
        reg_tree2 = build_reg_tree(xml_tree2)

        recursive_comparison(reg_tree1, reg_tree2)


def write_layer(layer_object, reg_number, notice, layer_type):

    layer_path = os.path.join(settings.JSON_ROOT, layer_type, reg_number)
    if not os.path.exists(layer_path):
        os.mkdir(layer_path)
    layer_file = os.path.join(layer_path, notice)
    json.dump(layer_object, open(layer_file, 'w'), indent=4,
              separators=(',', ':'))


def parser_driver(regulation_file,
                  check_terms=False,
                  correct_interps=False,
                  headerize_interps=False,
                  fix_missed_cites=False):
    with open(regulation_file, 'r') as f:
        reg_xml = f.read()
    xml_tree = etree.fromstring(reg_xml)

    # validate relative to schema
    validator = EregsValidator(settings.XSD_FILE)
    validator.validate_reg(xml_tree)

    if not validator.is_valid:
        for event in validator.events:
            print(str(event))
        sys.exit(0)

    reg_tree = build_reg_tree(xml_tree)
    reg_number = reg_tree.label[0]
    # we can correct interps right away if necessary
    if correct_interps:
        validator.insert_interp_markers(xml_tree, regulation_file)
    if headerize_interps:
        validator.headerize_interps(xml_tree, regulation_file)
    if fix_missed_cites:
        validator.fix_omitted_cites(xml_tree, regulation_file)

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
    notice_dict = build_notice(xml_tree)

    # if the validator had problems then we should report them and bail out

    validator.validate_terms(xml_tree, terms)
    validator.validate_internal_cites(xml_tree, internal_citations)
    if check_terms:
        validator.validate_term_references(xml_tree, terms, regulation_file)
    for event in validator.events:
        print(str(event))

    reg_tree.include_children = True
    reg_json = reg_tree.to_json()

    notice = xml_tree.find('.//{eregs}documentNumber').text
    version = os.path.split(regulation_file)[-1].replace('.xml', '')
    if notice != version:
        print('Notice ({}) different from version ({}), using version'.format(notice, version))
        notice = version

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
    write_layer(analysis, reg_number, notice, 'layer/analyses')
    write_layer(notice_dict, reg_number, notice, 'notice')

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('operation', action='store', choices=['parse', 'compare', 'graph'])
    parser.add_argument('regulation-files', nargs='*')
    parser.add_argument('notice-doc-numbers', nargs='*')
    parser.add_argument('--with-term-checks', nargs='?', default=False, type=bool)
    parser.add_argument('--correct-interp-markers', nargs='?', default=False, type=bool)
    parser.add_argument('--headerize-interps', nargs='?', default=False, type=bool)
    parser.add_argument('--fix-missed-cites', nargs='?', default=False, type=bool)

    args = vars(parser.parse_args())

    if args['operation'] == 'parse':
        if args['regulation-files'] is not None:
            for regfile in args['regulation-files']:
                print('Parsing {}'.format(regfile))
                parser_driver(regfile, args['with_term_checks'],
                              args['correct_interp_markers'],
                              args['headerize_interps'],
                              args['fix_missed_cites'])

    elif args['operation'] == 'compare':
        if args['regulation-files'] is not None:
            diff_driver(args['regulation-files'])

    elif args['operation'] == 'graph':
        if args['regulation-files'] is not None:
            for regfile in args['regulation-files']:
                build_graph(regfile)
