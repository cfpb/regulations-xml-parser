#!/usr/bin/env python
"""

"""
from __future__ import print_function

import json
import os
import sys

import click
from lxml import etree

from regulation.validation import EregsValidator
import regulation.settings as settings

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
from regulation.changes import process_changes, generate_diff

# Import regparser here with the eventual goal of breaking off the parts
# we're using in the RegML parser into a library both can share.
from regparser.federalregister import fetch_notice_json
from regparser.builder import LayerCacheAggregator, tree_and_builder

if (sys.version_info < (3, 0)):
    reload(sys)  # noqa
    sys.setdefaultencoding('UTF8')


# Utility Functions ####################################################

def find_file(file, is_notice=False, ecfr=False):
    """
        Find the given file in sources available in configured
        locations and read it.

        For example, if we're looking for a RegML file for version
        2222-33333 with the default arguments,
        settings.XML_ROOT/regulation will be searched for a matching
        document.

        With ecfr=True and regml=False, eCFR fr-notices
        (settings.LOCAL_XML_PATHS) will be searched.
    """
    # See if we need to find this file somewhere
    if not os.path.exists(file):
        if ecfr:
            ecfr_base = settings.LOCAL_XML_PATHS[0]
            file = os.path.join(ecfr_base, file)

        else:
            regml_base = settings.XML_ROOT
            if is_notice:
                regml_base = os.path.join(regml_base, 'notice')
            else:
                regml_base = os.path.join(regml_base, 'regulation')

            file = os.path.join(regml_base, file)

            if not file.endswith('.xml') and not os.path.isdir(file):
                file += '.xml'

    return file


def find_version(part, notice, is_notice=False):
    """ Wrap find file in a semantic sort of way to find a RegML version
        of a particular part """
    return find_file(os.path.join(part, notice), is_notice=is_notice)


def write_layer(layer_object, reg_number, notice, layer_type,
                diff_notice=None):
    """ Write a layer. """
    layer_path = os.path.join(settings.JSON_ROOT, layer_type, reg_number)
    if diff_notice is not None:
        layer_path = os.path.join(layer_path, diff_notice)
    if not os.path.exists(layer_path):
        os.makedirs(layer_path)
    layer_file = os.path.join(layer_path, notice)
    print("writing", layer_file)
    json.dump(layer_object, open(layer_file, 'w'), indent=4,
              separators=(',', ':'))


def generate_json(regulation_file, check_terms=False):
    with open(find_file(regulation_file), 'r') as f:
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
        print('Notice ({}) different from version ({}), '
              'using version'.format(notice, version))
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

    return reg_number, notice, xml_tree


# Main CLI Commands ####################################################

# Create a general CLI that can take additional comments
@click.group()
def cli():
    pass


# Perform validation on the given RegML file without any additional
# actions.
@cli.command()
@click.option('--check-terms', default=False)
@click.argument('file')
def validate(check_terms, file):
    """ Validate a RegML file """
    with open(find_file(file), 'r') as f:
        reg_xml = f.read()
    xml_tree = etree.fromstring(reg_xml)

    # Validate the file relative to schema
    validator = EregsValidator(settings.XSD_FILE)
    validator.validate_reg(xml_tree)

    if not validator.is_valid:
        for event in validator.events:
            print(str(event))
        sys.exit(0)

    # Validate regulation-specific documents
    if xml_tree.tag == '{eregs}regulation':
        terms = build_terms_layer(xml_tree)
        internal_citations = build_internal_citations_layer(xml_tree)

        validator.validate_terms(xml_tree, terms)
        validator.validate_internal_cites(xml_tree, internal_citations)

        if check_terms:
            validator.validate_term_references(xml_tree, terms, file)
        for event in validator.events:
            print(str(event))

    # Validate notice-specific documents
    if xml_tree.tag == '{eregs}notice':
        pass

    return validator


# Validate the given regulation file (or files) and generate the JSON
# output expected by regulations-core and regulations-site if the RegML
# validates.
# If multiple RegML files are given, and belong to the same regulation,
# diff JSON will be generated between them.
@cli.command('json')
@click.argument('regulation_files', nargs=-1, required=True)
@click.option('--check-terms', is_flag=True)
def json_command(regulation_files, check_terms=False):
    """ Generate JSON from RegML files """

    # If the "file" is a directory, assume we want to operate on all the
    # files in that directory in listing order
    if os.path.isdir(find_file(regulation_files[0])):
        regulation_dir = find_file(regulation_files[0])
        regulation_files = [os.path.join(regulation_dir, f)
                            for f in os.listdir(regulation_dir)]

    # Generate JSON for each version
    versions = {}
    reg_number = None
    for file in regulation_files:
        reg_number, notice, reg_xml_tree = generate_json(
            file, check_terms=check_terms)
        versions[notice] = reg_xml_tree

    # Generate diff JSON between each version
    # now build diffs - include "empty" diffs comparing a version to itself
    for left_version, left_tree in versions.items():
        for right_version, right_tree in versions.items():
            diff = generate_diff(left_tree, right_tree)
            write_layer(diff, reg_number, right_version, 'diff',
                        diff_notice=left_version)


# Given a notice, apply it to a previous RegML regulation verson to
# generate a new version in RegML.
@cli.command()
@click.argument('regulation_file')
@click.argument('notice_file')
def apply(regulation_file, notice_file):
    """ Apply notice changes """
    # Read the RegML starting point
    regulation_file = find_file(regulation_file)
    with open(regulation_file, 'r') as f:
        left_reg_xml = f.read()
    left_xml_tree = etree.fromstring(left_reg_xml)

    # Read the notice file
    notice_file = find_file(notice_file, is_notice=True)
    with open(notice_file, 'r') as f:
        notice_string = f.read()
    notice_xml = etree.fromstring(notice_string)

    # Process the notice changeset
    new_xml_tree = process_changes(left_xml_tree, notice_xml)

    # Write the new xml tree
    new_xml_string = etree.tostring(new_xml_tree,
                                    pretty_print=True,
                                    xml_declaration=True,
                                    encoding='UTF-8')
    new_path = os.path.join(
        os.path.dirname(regulation_file),
        os.path.basename(notice_file))
    with open(new_path, 'w') as f:
        print("Writing regulation to {}".format(new_path))
        f.write(new_xml_string)


@cli.command()
@click.argument('title')
@click.argument('part')
def noticelist(title, part):
    """ List notices for regulation title/part """
    notices = fetch_notice_json(title, part, only_final=True)
    doc_numbers = [n['document_number'] for n in notices]
    for number in doc_numbers:
        print(number)


# eCFR Convenience Commands ############################################

# Wrap the eCFR parser as a library for the purposes of our workflow
@cli.command()
@click.argument('title', type=int)
@click.argument('file')
@click.option('--act-section', default=0, type=int)
@click.option('--act-title', default=0, type=int)
@click.option('--with-all-versions', is_flag=True,
              help="do not output version reg trees")
@click.option('--without-versions', is_flag=True,
              help="do not output any version reg trees")
@click.option('--without-notices', is_flag=True,
              help="do not output any notice changesets")
@click.option('--only-notice', default=None,
              help="only write output for this notice number")
def ecfr(title, file, act_title, act_section,
         with_all_versions=False, without_versions=False,
         without_notices=False, only_notice=None):
    """ Parse eCFR into RegML """

    # Get the tree and layers
    reg_tree, builder = tree_and_builder(
        file, title, writer_type='XML')
    layer_cache = LayerCacheAggregator()
    layers = builder.generate_layers(reg_tree,
                                     [act_title, act_section],
                                     layer_cache)

    # Do the first version
    print("Version %s", builder.doc_number)
    if (only_notice is not None and builder.doc_number == only_notice) \
            or only_notice is None:
        if not without_versions:
            builder.write_regulation(reg_tree, layers=layers)

    for last_notice, old, new_tree, notices in builder.revision_generator(
            reg_tree):
        version = last_notice['document_number']
        print("Version %s", version)
        builder.doc_number = version
        layers = builder.generate_layers(new_tree,
                                         [act_title, act_section],
                                         layer_cache,
                                         notices)
        if (only_notice is not None and version == only_notice) or \
                only_notice is None:
            if with_all_versions:
                builder.write_regulation(new_tree, layers=layers)
            if not without_notices:
                builder.write_notice(version,
                                     old_tree=old,
                                     reg_tree=new_tree,
                                     layers=layers)
        layer_cache.invalidate_by_notice(last_notice)
        layer_cache.replace_using(new_tree)
        del last_notice, old, new_tree, notices     # free some memory


if __name__ == "__main__":
    cli()
