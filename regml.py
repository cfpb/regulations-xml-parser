#!/usr/bin/env python
"""

"""
from __future__ import print_function

import glob
import json
import os
import sys

import click
from lxml import etree
from termcolor import colored, cprint

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


def get_validator(xml_tree):
    # Validate the file relative to schema
    validator = EregsValidator(settings.XSD_FILE)
    validator.validate_reg(xml_tree)

    if not validator.is_valid:
        for event in validator.events:
            print(str(event))
        sys.exit(0)

    return validator


def generate_json(regulation_file, check_terms=False):
    with open(find_file(regulation_file), 'r') as f:
        reg_xml = f.read()
    xml_tree = etree.fromstring(reg_xml)

    # Validate the file relative to schema
    validator = get_validator(xml_tree)

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
    validator.validate_keyterms(xml_tree)
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
@click.argument('file')
@click.option('--no-terms', is_flag=True, 
    help="don't try to validate terms")
@click.option('--no-citations', is_flag=True, 
    help="don't try to validate citations")
@click.option('--no-keyterms', is_flag=True, 
    help="don't try to validate keyterms")
def validate(file, no_terms=False, no_citations=False, no_keyterms=False):
    """ Validate a RegML file """
    file = find_file(file)
    with open(file, 'r') as f:
        reg_xml = f.read()
    xml_tree = etree.fromstring(reg_xml)

    # Validate the file relative to schema
    validator = get_validator(xml_tree)

    # Validate regulation-specific documents
    if xml_tree.tag == '{eregs}regulation':
        terms = build_terms_layer(xml_tree)
        internal_citations = build_internal_citations_layer(xml_tree)

        if not no_terms:
            validator.validate_terms(xml_tree, terms)
        if not no_citations:
            validator.validate_internal_cites(xml_tree, internal_citations)
        if not no_keyterms:
            validator.validate_keyterms(xml_tree)

        for event in validator.events:
            print(str(event))

    # Validate notice-specific documents
    if xml_tree.tag == '{eregs}notice':
        pass

    return validator


@cli.command('check-terms')
@click.argument('file')
@click.option('--label')
@click.option('--term')
def check_terms(file, label=None, term=None):
    """ Check the terms in a RegML file """

    file = find_file(file)
    with open(file, 'r') as f:
        reg_xml = f.read()
    xml_tree = etree.fromstring(reg_xml)

    if xml_tree.tag == '{eregs}notice':
        print("Cannot check terms in notice files")
        sys.exit(1)

    # Validate the file relative to schema
    validator = get_validator(xml_tree)

    terms = build_terms_layer(xml_tree)
    validator.validate_terms(xml_tree, terms)
    validator.validate_term_references(xml_tree, terms, file,
            label=label, term=term)


@cli.command()
@click.argument('file')
@click.option('--label')
def check_interp_targets(file, label=None):
    """ Check the interpretations targets in a RegML file """

    file = find_file(file)
    with open(file, 'r') as f:
        reg_xml = f.read()
    xml_tree = etree.fromstring(reg_xml)

    if xml_tree.tag == '{eregs}notice':
        print("Cannot check terms in notice files")
        sys.exit(1)

    # Validate the file relative to schema
    validator = get_validator(xml_tree)
    validator.validate_interp_targets(xml_tree, file, label=label)
    

@cli.command('check-changes')
@click.argument('file')
@click.option('--label')
def check_changes(file, label=None):
    """ Check for duplicate changes in a notice RegML file """
    file = find_file(file, is_notice=True)
    with open(file, 'r') as f:
        reg_xml = f.read()
    xml_tree = etree.fromstring(reg_xml)

    if xml_tree.tag != '{eregs}notice':
        print("Can only check changes in notice files")
        sys.exit(1)

    # Validate the file relative to schema
    validator = get_validator(xml_tree)
    validator.remove_duplicate_changes(xml_tree, file, label=label)
    

# Validate the given regulation file (or files) and generate the JSON
# output expected by regulations-core and regulations-site if the RegML
# validates.
# If multiple RegML files are given, and belong to the same regulation,
# diff JSON will be generated between them.
@cli.command('json')
@click.argument('regulation_files', nargs=-1, required=True)
@click.option('--check-terms', is_flag=True)
def json_command(regulation_files, from_notices=[], check_terms=False):
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
@cli.command('apply-notice')
@click.argument('regulation_file')
@click.argument('notice_file')
def apply_notice(regulation_file, notice_file):
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


# Given a regulation title and part number, prompts the user to select
# which notice to stop at and applies all notices applicable to the reg
@cli.command('apply-through')
@click.argument('cfr_title')
@click.argument('cfr_part')
@click.option('--through',
              help="Skips prompt and applies notices through given notice number " +
                   "(e.g. --through YYYY-#####")
def apply_through(cfr_title, cfr_part, through=None):
    # Get list of notices that apply to this reg
    # Look for locally available notices
    regml_notice_dir = os.path.join(settings.XML_ROOT, 'notice', cfr_part, '*.xml')
    regml_notice_files = glob.glob(regml_notice_dir)

    regml_notices = []
    for notice_file in regml_notice_files:
        file_name = os.path.join(notice_file)
        with open(file_name, 'r') as f:
            notice_xml = f.read()
        xml_tree = etree.fromstring(notice_xml)
        doc_number = xml_tree.find(
            './{eregs}preamble/{eregs}documentNumber').text
        effective_date = xml_tree.find(
            './{eregs}preamble/{eregs}effectiveDate').text
        applies_to = xml_tree.find(
            './{eregs}changeset').get('leftDocumentNumber')
        regml_notices.append((doc_number, effective_date, applies_to, file_name))

    regml_notices.sort(key=lambda n: n[1])
    
    regs = [nn[2] for nn in regml_notices]
    regs.sort()

    # Generate prompt for user
    print(colored("\nAvailable notices for reg {}:".format(cfr_part),
          attrs=['bold']))
    print("{:>3}. {:<22}(Initial version)".format(0, regs[0]))
    for kk in range(len(regml_notices)):
        print("{0:>3}. {1[0]:<22}(Effective: {1[1]})".format(kk+1,
                                               regml_notices[kk]))
    print()

    # Possible answers are blank (all), the numbers, or the notice names
    possible_indices = [str(kk) for kk in range(len(regml_notices) + 1)]
    possible_notices = [nn[0] for nn in regml_notices]

    # If notice number is supplied, use that one
    if through is not None:
        print("Command-line option selected notice '{}'".format(through))
        answer = through
    else: 
        # Get user input to specify end version
        answer = None
        while answer not in [""] + possible_indices + possible_notices: 
            answer = raw_input('Press enter to apply all or enter notice number: [all] ')
        # print("Answer: '{}'".format(answer))

    if len(answer) == 0:
        # Apply notices
        last_ver_idx = len(regml_notices) - 1
    elif answer is "0":
        # Cancel - this is just the initial version
        print(colored("CANCELED: Version", attrs=['bold']),
              colored("{}".format(regs[0]), 'yellow', attrs=['bold']),
              colored("is the initial version - no changes have been made.", attrs=['bold']))
        return
    elif answer in possible_indices:
        # Apply notices through answer-1 to adjust for the initial ver offset
        last_ver_idx = int(answer) - 1
    elif answer in possible_notices:
        # Find index to stop at in notice list
        last_ver_idx = possible_notices.index(answer)
    else:
        print(colored("ERROR: Notice", attrs=['bold']),
              colored("{}".format(answer), 'red', attrs=['bold']),
              colored("does not exist - no changes have been made.", attrs=['bold']))
        return

    print(colored("\nApplying notices through {0[0]}\n".format(regml_notices[last_ver_idx]),
          attrs=['bold']))

    # Perform the notice application process
    reg_path = os.path.abspath(os.path.join(settings.XML_ROOT,
                                            'regulation',
                                            cfr_part,
                                            '{}.xml'.format(regs[0])))
    print("Opening initial version {}".format(reg_path))
    regulation_file = find_file(reg_path)
    with open(regulation_file, 'r') as f:
        left_reg_xml = f.read()
    left_xml_tree = etree.fromstring(left_reg_xml)

    kk = 1
    prev_tree = left_xml_tree
    for notice in regml_notices[:last_ver_idx+1]:
        doc_number, effective_date, prev_notice, file_name = notice

        print("[{}] Applying notice {} to version {}".format(kk,
                                                             doc_number,
                                                             prev_notice))

        # Open the notice file
        notice_file = find_file(file_name, is_notice=True)
        with open(notice_file, 'r') as f:
            notice_string = f.read()
        notice_xml = etree.fromstring(notice_string)

        # Process the notice changeset
        new_xml_tree = process_changes(prev_tree, notice_xml)

        # Write the new xml tree
        new_xml_string = etree.tostring(new_xml_tree,
                                        pretty_print=True,
                                        xml_declaration=True,
                                        encoding='UTF-8')
        new_path = os.path.join(
            os.path.dirname(regulation_file),
            os.path.basename(notice_file))
        with open(new_path, 'w') as f:
            print("[{}] Writing regulation to {}".format(kk, new_path))
            f.write(new_xml_string)

        prev_tree = new_xml_tree
        kk += 1


# Given a notice, apply it to a previous RegML regulation verson to
# generate a new version in RegML.
@cli.command('notice-changes')
@click.argument('notice_file')
def notice_changes(notice_file):
    """ List changes in a given notice file """
    # Read the notice file
    notice_file = find_file(notice_file, is_notice=True)
    with open(notice_file, 'r') as f:
        notice_string = f.read()
    notice_xml = etree.fromstring(notice_string)
    doc_number = notice_xml.find(
            './{eregs}preamble/{eregs}documentNumber').text

    print(colored("{} makes the following changes:".format(doc_number), 
                  attrs=['bold']))

    changes = notice_xml.findall('./{eregs}changeset/{eregs}change')
    for change in changes:
        label = change.get('label')
        op = change.get('operation')
        if op == 'added':
            print('\t', colored(op, 'green'), label)
        if op == 'modified':
            print('\t', colored(op, 'yellow'), label)
        if op == 'deleted':
            print('\t', colored(op, 'red'), label)


# Given a regulation part number, version, and a set of notices
# apply the notices to the regulation file in sequential order,
# producing intermediate XML files along the way.
@cli.command('apply-notices')
@click.argument('cfr_part')
@click.argument('version')
@click.argument('notices', nargs=-1)
def apply_notices(cfr_part, version, notices):
    regulation_file = find_file(os.path.join(cfr_part, version))
    with open(regulation_file, 'r') as f:
        left_reg_xml = f.read()
    left_xml_tree = etree.fromstring(left_reg_xml)

    prev_notice = version
    prev_tree = left_xml_tree
    for notice in notices:
        print('Applying notice {} to version {}'.format(notice, prev_notice))
        notice_file = find_file(os.path.join(cfr_part, notice), is_notice=True)
        with open(notice_file, 'r') as f:
            notice_string = f.read()
        notice_xml = etree.fromstring(notice_string)

        # Process the notice changeset
        new_xml_tree = process_changes(prev_tree, notice_xml)

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

        prev_notice = notice
        prev_tree = new_xml_tree


@cli.command()
@click.argument('title')
@click.argument('part')
@click.option('--from-fr', is_flag=True,
              help="check for notices in the Federal Register")
def versions(title, part, from_fr=False, from_regml=True):
    """ List notices for regulation title/part """

    if from_fr:
        # Get notices from the FR
        fr_notices = fetch_notice_json(title, part, only_final=True)
        print(colored("The Federal Register reports the following "
                      "final notices:", attrs=['bold']))
        for notice in fr_notices:
            print("\t", notice['document_number'])
            print("\t\tinitially effective on", notice['effective_on'])

    # Look for locally available notices
    regml_notice_dir = os.path.join(settings.XML_ROOT, 'notice', part, '*.xml')
    regml_notice_files = glob.glob(regml_notice_dir)
    # regml_notice_files = os.listdir(regml_notice_dir)
    print(colored("RegML Notices are available for:", attrs=['bold']))
    regml_notices = []
    for notice_file in regml_notice_files:
        with open(os.path.join(notice_file), 'r') as f:
            notice_xml = f.read()
        xml_tree = etree.fromstring(notice_xml)
        doc_number = xml_tree.find(
            './{eregs}preamble/{eregs}documentNumber').text
        effective_date = xml_tree.find(
            './{eregs}preamble/{eregs}effectiveDate').text
        applies_to = xml_tree.find(
            './{eregs}changeset').get('leftDocumentNumber')
        regml_notices.append((doc_number, effective_date, applies_to))

    regml_notices.sort(key=lambda n: n[1])
    for notice in regml_notices:
        print("\t", notice[0])
        print("\t\teffective on", notice[1])
        print("\t\tapplies to", notice[2])

        # Verify that there's a logical sequence of applies_to
        index = regml_notices.index(notice)
        if index == 0:
            continue

        previous_notice = regml_notices[regml_notices.index(notice)-1]
        if previous_notice[0] != notice[2]:
            print(colored("\t\tWarning: {} does not apply to "
                          "previous notice {}".format(
                                notice[0], 
                                previous_notice[0]), 'yellow'))


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
    last_version = builder.doc_number
    print("Version {}".format(last_version))
    if (only_notice is not None and builder.doc_number == only_notice) \
            or only_notice is None:
        if not without_versions:
            builder.write_regulation(reg_tree, layers=layers)

    for last_notice, old, new_tree, notices in builder.revision_generator(
            reg_tree):
        version = last_notice['document_number']
        print("Version {}".format(version))
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
                                     layers=layers,
                                     last_version=last_version)
        layer_cache.invalidate_by_notice(last_notice)
        layer_cache.replace_using(new_tree)
        last_version = version
        del last_notice, old, new_tree, notices     # free some memory


if __name__ == "__main__":
    cli()
