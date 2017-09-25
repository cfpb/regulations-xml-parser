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
from itertools import permutations

from regulation.validation import EregsValidator
import regulation.settings as settings
from regulation.diff import diff_files

from regulation.tree import (
    build_analysis,
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
    build_toc_layer
)
from regulation.changes import (
    process_changes,
    process_analysis,
    generate_diff,
    rectify_analysis
)

# Import regparser here with the eventual goal of breaking off the parts
# we're using in the RegML parser into a library both can share.

from regparser.federalregister import fetch_notice_json
from regparser.builder import (
    Builder,
    Checkpointer,
    LayerCacheAggregator,
    tree_and_builder
)
from regparser.notice.compiler import compile_regulation


if (sys.version_info < (3, 0)):
    reload(sys)  # noqa
    sys.setdefaultencoding('UTF8')


# Utility Functions ####################################################

def base_path(is_notice=False):
    """ Return the base RegML path based on our configuration. """
    regml_base = settings.XML_ROOT
    if is_notice:
        regml_base = os.path.join(regml_base, 'notice')
    else:
        regml_base = os.path.join(regml_base, 'regulation')

    return regml_base


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
            file = os.path.join(base_path(is_notice=is_notice), file)
            if not file.endswith('.xml') and not os.path.isdir(file):
                file += '.xml'

    return file


def find_all(part, is_notice=False):
    """ Find all regulation RegML files for the given part.

        If is_notice is True, all notice RegML files will be returned. """
    regml_base = base_path(is_notice=is_notice)
    regulation_pattern = os.path.join(regml_base, part, '*.xml')
    files = glob.glob(regulation_pattern)
    return files


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


def get_validator(xml_tree, raise_instead_of_exiting=False):
    # Validate the file relative to schema
    validator = EregsValidator(settings.XSD_FILE)
    validator.validate_reg(xml_tree)

    if not validator.is_valid:
        for event in validator.events:
            print(str(event))
        if raise_instead_of_exiting:
            raise event
        else:
            sys.exit(int(validator.has_critical_errors))

    return validator


def generate_json(regulation_file, check_terms=False):
    with open(find_file(regulation_file), 'r') as f:
        reg_xml = f.read()
    parser = etree.XMLParser(huge_tree=True)
    xml_tree = etree.fromstring(reg_xml, parser)

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

# Create a general CLI that can take additional commands
@click.group()
def cli():
    pass


# Perform validation on the given RegML file without any additional
# actions.
@cli.command('validate')
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
    parser = etree.XMLParser(huge_tree=True)
    xml_tree = etree.fromstring(reg_xml, parser)

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

    if validator.has_critical_errors:
        print('Validation failed with critical errors.')
        sys.exit(1)


@cli.command('check-terms')
@click.argument('file')
@click.option('--label')
@click.option('--term')
@click.option('--with-notice')
def check_terms(file, label=None, term=None, with_notice=None):
    """ Check the terms in a RegML file """

    file = find_file(file)
    with open(file, 'r') as f:
        reg_string = f.read()
    parser = etree.XMLParser(huge_tree=True)
    reg_tree = etree.fromstring(reg_string, parser)

    if reg_tree.tag == '{eregs}notice':
        print("Cannot check terms in notice files directly.")
        print("Use a regulation file and --with-notice to specify the notice that applies.")
        sys.exit(1)

    # If we're given a notice, apply it to the given regulation file,
    # then check terms in the result and write it out to the notice file
    # as changes.
    notice_tree = None
    if with_notice is not None:
        # file is changed here so the term checker will write the notice
        # instead of the regulation
        file = find_file(with_notice, is_notice=True)
        with open(file, 'r') as f:
            notice_xml = f.read()
        notice_tree = etree.fromstring(notice_xml)

        # Process the notice changeset
        print(colored('Applying notice...', attrs=['bold']))
        reg_tree = process_changes(reg_tree, notice_tree)

    # Validate the file relative to schema
    validator = get_validator(reg_tree)

    terms = build_terms_layer(reg_tree)
    validator.validate_terms(reg_tree, terms)
    validator.validate_term_references(reg_tree, terms, file,
            label=label, term=term, notice=notice_tree)


@cli.command()
@click.argument('file')
@click.option('--label')
@click.option('--is-notice', is_flag=True)
def check_interp_targets(file, label=None, is_notice=False):
    """ Check the interpretations targets in a RegML file """

    file = find_file(file, is_notice=is_notice)
    with open(file, 'r') as f:
        reg_xml = f.read()
    parser = etree.XMLParser(huge_tree=True)
    xml_tree = etree.fromstring(reg_xml, parser)

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
    parser = etree.XMLParser(huge_tree=True)
    xml_tree = etree.fromstring(reg_xml, parser)

    if xml_tree.tag != '{eregs}notice':
        print("Can only check changes in notice files")
        sys.exit(1)

    # Validate the file relative to schema
    validator = get_validator(xml_tree)
    validator.remove_duplicate_changes(xml_tree, file, label=label)
    validator.remove_empty_refs(xml_tree, file)


@cli.command('check-keyterms')
@click.argument('file')
@click.option('--with-notice')
def check_keyterms(file, with_notice=None):
    """ Check for keyterm fragments in a RegML file

        If --with-notice is used, only *new* keyterm fragments
        introduced in the notice will be given. """

    file = find_file(file)
    with open(file, 'r') as f:
        reg_string = f.read()
    parser = etree.XMLParser(huge_tree=True)
    reg_tree = etree.fromstring(reg_string, parser)

    if reg_tree.tag == '{eregs}notice':
        print("Cannot check terms in notice files directly.")
        print("Use a regulation file and --with-notice to specify the notice that applies.")
        sys.exit(1)

    # If we're given a notice, apply it to the given regulation file,
    # then check terms in the result and write it out to the notice file
    # as changes.
    notice_tree = None
    if with_notice is not None:
        # file is changed here so the term checker will write the notice
        # instead of the regulation
        file = find_file(with_notice, is_notice=True)
        with open(file, 'r') as f:
            notice_xml = f.read()
        notice_tree = etree.fromstring(notice_xml)

        # Process the notice changeset
        print(colored('Applying notice...', attrs=['bold']))
        reg_tree = process_changes(reg_tree, notice_tree)

    # Validate the file relative to schema
    validator = get_validator(reg_tree)
    validator.validate_keyterms(reg_tree, notice_tree=notice_tree)

    for event in validator.events:
        print(str(event))


@cli.command('migrate-analysis')
@click.argument('cfr_title')
@click.argument('cfr_part')
def migrate_analysis(cfr_title, cfr_part):
    """ Migrate analysis from its context to top-level """

    # Prompt user to be sure they want to do this
    print(colored('This will irrevocably modify all regulation and notice files for this regulation. '
                  'Is this ok?', 'red'))
    answer = None
    while answer not in ['y', 'n']:
        answer = raw_input('Migrate all analysis? y/n: ')
    if answer != 'y':
        return

    # Migrate regulation files
    regml_reg_files = find_all(cfr_part)
    for reg_file in regml_reg_files:
        print(reg_file)
        file_name = os.path.join(reg_file)
        with open(file_name, 'r') as f:
            reg_xml = f.read()
        parser = etree.XMLParser(huge_tree=True)
        xml_tree = etree.fromstring(reg_xml, parser)
        validator = EregsValidator(settings.XSD_FILE)
        validator.migrate_analysis(xml_tree, file_name)
        validator.validate_reg(xml_tree)

    # Migrate notices
    regml_notice_files = find_all(cfr_part, is_notice=True)
    regml_notices = []
    for notice_file in regml_notice_files:
        print(notice_file)
        file_name = os.path.join(notice_file)
        with open(file_name, 'r') as f:
            reg_xml = f.read()
        parser = etree.XMLParser(huge_tree=True)
        xml_tree = etree.fromstring(reg_xml, parser)
        validator = EregsValidator(settings.XSD_FILE)
        validator.migrate_analysis(xml_tree, file_name)
        validator.validate_reg(xml_tree)


#
@cli.command('fix-analysis')
@click.argument('file')
@click.option('--always-save', is_flag=True)
# @click.option('--label')
def fix_analysis(file, always_save=False):
    """Checks and fixes the analysis in a notice RegML file"""
    file = find_file(file, is_notice=True)
    with open(file, 'r') as f:
        reg_xml = f.read()
    parser = etree.XMLParser(huge_tree=True)
    xml_tree = etree.fromstring(reg_xml, parser)

    if xml_tree.tag != '{eregs}notice':
        print("Can only check changes in notice files")
        sys.exit(1)

    # Parse through the analysis tree
    print("Checking analysis tree")
    new_xml_tree = rectify_analysis(xml_tree)

    if new_xml_tree is None:
        print(colored("ERROR: No analysis found in notice.",
              attrs=['bold']))
        return

    # Validate the file relative to schema
    print("Validating updated notice xml")
    validator = get_validator(new_xml_tree)
    print("Validation complete!")

    # Write the new xml tree
    new_xml_string = etree.tostring(new_xml_tree,
                                    pretty_print=True,
                                    xml_declaration=True,
                                    encoding='UTF-8')

    # Prompt user whether to update the notice
    if always_save:
        answer = "y"
    else:
        answer = None

    while answer not in ["", "y", "n"]:
        answer = raw_input('Save updated analysis to notice file? y/n [y] ')

    if answer in ["", "y"]:
        # Save the new xml tree to the original file
        print("Writing regulation to {}".format(file))
        with open(file, 'w') as f:
            f.write(new_xml_string)
    else:
        # Cancel save
        print("Canceling analysis fixes - changes have not been saved.")


# Validate the given regulation file (or files) and generate the JSON
# output expected by regulations-core and regulations-site if the RegML
# validates.
# If multiple RegML files are given, and belong to the same regulation,
# diff JSON will be generated between them.
@cli.command('json')
@click.argument('regulation_files', nargs=-1, required=True)
@click.option('--check-terms', is_flag=True)
@click.option('--skip_diffs', is_flag=True, help="Suppresses generation of diffs between versions.")
def json_command(regulation_files, from_notices=[], check_terms=False, skip_diffs=False):
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
        print("Building JSON for {}".format(file))
        reg_number, notice, reg_xml_tree = generate_json(
            file, check_terms=check_terms)
        versions[notice] = reg_xml_tree

    # Generate diff JSON between each version
    # now build diffs - include "empty" diffs comparing a version to itself
    if not skip_diffs:
        print(colored("\nBuilding inter-version diffs.", attrs=['bold']))
        print(colored("WARNING: This may take an extended period of time.",
              'red', attrs=['bold']))
        print("To skip diff creation, use the --skip_diffs command line argument.\n")
        for left_version, left_tree in versions.items():
            for right_version, right_tree in versions.items():
                diff = generate_diff(left_tree, right_tree)
                write_layer(diff, reg_number, right_version, 'diff',
                            diff_notice=left_version)


# Given a regulation title and part number, prompts the user to select
# which notice to stop at and applies all notices applicable to the reg
@cli.command('json-through')
@click.argument('cfr_title')
@click.argument('cfr_part')
@click.option('--start', help="Performs JSON starting from document number" +
              "(format: --from YYYY-#####). " +
              "Specify -1 to use first document number. " +
              "If no 'through' specified, goes til end.")
@click.option('--through',
              help="Performs JSON through given document number " +
                   "(e.g. --through YYYY-#####). " +
                   "If no 'start' specified, starts from beginning.")
@click.option('--skip_diffs', is_flag=True,
              help="Suppresses generation of diffs between versions.")
@click.option('--suppress_output', is_flag=True,
              help="Suppresses output except for errors")
@click.pass_context
def json_through(ctx, cfr_title, cfr_part, start=None, through=None, suppress_output=False, skip_diffs=False):
    # Get list of available regs
    regml_reg_files = find_all(cfr_part)

    regml_regs = []
    regulation_files = []
    for reg_file in regml_reg_files:
        file_name = os.path.join(reg_file)
        with open(file_name, 'r') as f:
            reg_xml = f.read()
        parser = etree.XMLParser(huge_tree=True)
        xml_tree = etree.fromstring(reg_xml, parser)
        doc_number = xml_tree.find(
            './{eregs}preamble/{eregs}documentNumber').text
        effective_date = xml_tree.find(
            './{eregs}preamble/{eregs}effectiveDate').text
        regml_regs.append((doc_number, effective_date, file_name))

    regml_regs.sort(key=lambda n: n[1])
    regulation_files = [r[2] for r in regml_regs]

    # Generate prompt for user
    print(colored("\nAvailable RegML documents for reg {}:".format(cfr_part),
          attrs=['bold']))
    for kk in range(len(regml_regs)):
        print("{0:>3}. {1[0]:<22}(Effective: {1[1]})".format(kk,
                                                             regml_regs[kk]))
    print()

    # Possible answers are blank (all), the numbers, or the doc names
    possible_indices = [str(kk) for kk in range(len(regml_regs))]
    possible_regs = [nn[0] for nn in regml_regs]

    if start == '-1':
        start = possible_regs[0]

    # If number is supplied, use that one
    if through is not None:
        if start is not None:
            print("Command-line: selected documents '{}'-'{}'".format(start, through))

        else:
            print("Command-line: selected document number '{}'".format(through))

        answer = through
    elif start is not None:
        print("Command-line: selected start document number '{}'".format(start))
        answer = possible_regs[-1] # JSON all documents
    else:
        # Get user input to specify end version
        answer = None
        while answer not in [""] + possible_indices + possible_regs:
            answer = raw_input('Press enter to apply all or enter document number: [all] ')
        print("Answer: '{}'".format(answer))

    if len(answer) == 0:
        # Apply JSON to all documents
        last_ver_idx = len(regml_regs) - 1
    elif answer in possible_indices:
        # Apply through answer
        last_ver_idx = int(answer)
    elif answer in possible_regs:
        # Find index to stop at in list
        last_ver_idx = possible_regs.index(answer)
    else:
        print(colored("ERROR: Document", attrs=['bold']),
              colored("{}".format(answer), 'red', attrs=['bold']),
              colored("does not exist - no changes have been made.", attrs=['bold']))
        return

    # Support for telling user what we're doing on whether or not diffs will be created.
    if skip_diffs:
        skip_text = ", skipping creation of diffs."
    else:
        skip_text = ", including diffs."

    if start is not None:
        if start in possible_regs:
            first_ver_idx = possible_regs.index(start)
        else:
            print(colored("ERROR: Document chosen for start", attrs=['bold']),
                  colored("{}".format(start), 'red', attrs=['bold']),
                  colored("does not exist - no changes have been made.", attrs=['bold']))
            return

        # Check that first_ver_idx < last_ver_idx
        if first_ver_idx > last_ver_idx:
            print(colored("ERROR: Start document", attrs=['bold']),
                  colored("{}".format(regml_regs[first_ver_idx][0]), 'red', attrs=['bold']),
                  colored("is not before 'through' notice"),
                  colored("{}".format(regml_regs[last_ver_idx][0]), 'red', attrs=['bold']))
            return

        print(colored("\nApplying JSON from {1[0]} through {0[0]}{2}\n".format(
                      regml_regs[last_ver_idx], regml_regs[first_ver_idx], skip_text),
              attrs=['bold']))

        # Perform the json application process
        # Unlike apply-through, since json outputs its own command line output, here we
        # reuse the existing json structure
        ctx.invoke(json_command,
                   regulation_files=regulation_files[first_ver_idx:last_ver_idx+1],
                   skip_diffs=skip_diffs)

    else:
        print(colored("\nApplying JSON through {0[0]}{1}\n".format(
                      regml_regs[last_ver_idx], skip_text),
              attrs=['bold']))

        # Perform the json application process
        # Unlike apply-through, since json outputs its own command line output, here we
        # reuse the existing json structure
        # json_command(regulation_files[:last_ver_idx+1], skip_diffs=skip_diffs)
        ctx.invoke(json_command,
                   regulation_files=regulation_files[:last_ver_idx+1],
                   skip_diffs=skip_diffs)


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
    parser = etree.XMLParser(huge_tree=True)
    left_xml_tree = etree.fromstring(left_reg_xml, parser)

    # Read the notice file
    notice_file = find_file(notice_file, is_notice=True)
    with open(notice_file, 'r') as f:
        notice_string = f.read()
    parser = etree.XMLParser(huge_tree=True)
    notice_xml = etree.fromstring(notice_string, parser)

    # Validate the files
    regulation_validator = get_validator(left_xml_tree)
    notice_validator = get_validator(notice_xml)

    # Process the notice changeset
    new_xml_tree = process_changes(left_xml_tree, notice_xml)

    # Add in any new analysis
    new_xml_tree = process_analysis(new_xml_tree, notice_xml)

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


# Given a regulation part number, iterate over all existing *regulations* (not notices)
# and write out the XML files representing the diffs.
@cli.command('generate-diff-xml')
@click.argument('cfr_part')
@click.option('--versions',
              help="If provided, supplies the list of regulations from which to generate diffs",
              multiple=True)
def generate_diff_xml(cfr_part, versions=None):

    def version(regml_file):
        return os.path.split(regml_file)[-1].replace('.xml', '')

    if versions:
        regml_files = [item for item in find_all(cfr_part) if version(item) not in versions]
    else:
        regml_files = find_all(cfr_part)

    import time

    diff_base = os.path.join(settings.XML_ROOT, 'diff', cfr_part)
    if not os.path.exists(diff_base):
        os.mkdir(diff_base)

    start_time = time.clock()
    for pair in permutations(regml_files, 2):
        tree, left_version, right_version = diff_files(pair[0], pair[1])
        diff_path = os.path.join(diff_base, '{}:{}.xml'.format(left_version, right_version))
        with open(diff_path, 'w') as f:
            print('Writing diff from {} to {} to {}'.format(left_version, right_version, diff_path))
            f.write(etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8'))
    end_time = time.clock()
    print('Diff calculation for part {} took {} minutes'.format(cfr_part, (end_time - start_time) / 60.0))

# Given a regulation title and part number, prompts the user to select
# which notice to stop at and applies all notices applicable to the reg
@cli.command('apply-through')
@click.argument('cfr_title')
@click.argument('cfr_part')
@click.option('--through',
              help="Skips prompt and applies notices through given notice number " +
                   "(e.g. --through YYYY-#####)")
@click.option('--fix-notices',
              help="If set to True, use the validator to fix notices as you apply them.")
@click.option('--skip-fix-notices', multiple=True,
              help="Document numbers of notices to skip. Specify this multiple times because"
                   "nargs='*' doesn't work in click.")
@click.option('--skip-fix-notices-through',
              help='Skip fixing notices through the specified document number.')
def apply_through(cfr_title, cfr_part, start=None, through=None,
                  fix_notices=False, skip_fix_notices=[],
                  skip_fix_notices_through=None):
    # Get list of notices that apply to this reg
    # Look for locally available notices
    regml_notice_files = find_all(cfr_part, is_notice=True)

    regml_notices = []
    for notice_file in regml_notice_files:
        file_name = os.path.join(notice_file)
        with open(file_name, 'r') as f:
            notice_xml = f.read()
        parser = etree.XMLParser(huge_tree=True)

        try:
            xml_tree = etree.fromstring(notice_xml, parser)
        except etree.XMLSyntaxError as e:
            print(colored('Syntax error in {}'.format(notice_file), 'red'))
            print(e)
            return

        doc_number = xml_tree.find(
            './{eregs}preamble/{eregs}documentNumber').text
        effective_date = xml_tree.find(
            './{eregs}preamble/{eregs}effectiveDate').text
        applies_to = xml_tree.find(
            './{eregs}changeset').get('leftDocumentNumber')
        if applies_to is None:
            # Major problem here
            print(colored("Error locating"),
                  colored("leftDocumentNumber", attrs=['bold']),
                  colored("attribute in"),
                  colored("{}".format(doc_number), 'red',
                          attrs=['bold']))
            return

        regml_notices.append((doc_number, effective_date, applies_to, file_name))

    if cfr_part in settings.CUSTOM_NOTICE_ORDER:
        order = settings.CUSTOM_NOTICE_ORDER[cfr_part]
        regml_notices.sort(key=lambda n: order.index(n[0]))

    else:
        regml_notices.sort(key=lambda n: n[1])

    regs = [nn[2] for nn in regml_notices]
    regs.sort()

    # If no notices found, issue error message
    if not regml_notices:
        print(colored("\nNo available notices for reg {} in part {}".format(cfr_part, cfr_title)))
        return

    # If initial version is not findable, issue error message
    if regs[0] is None:
        print(colored("\nError reading initial version and apply order for reg {} in part {}. No changes have been made.".format(cfr_part, cfr_title),
                      attrs=['bold']))
        return

    # Generate prompt for user
    print(colored("\nAvailable notices for reg {}:".format(cfr_part),
          attrs=['bold']))
    print("{:>3}. {:<22}(Initial version)".format(0, regs[0]))
    # Process notices found
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
    parser = etree.XMLParser(huge_tree=True)
    left_xml_tree = etree.fromstring(left_reg_xml, parser)

    kk = 1
    prev_tree = left_xml_tree
    for notice in regml_notices[:last_ver_idx+1]:
        doc_number, effective_date, prev_notice, file_name = notice

        print("[{}] Applying notice {} from {} to version {}".format(kk,
                                                                     doc_number,
                                                                     file_name,
                                                                     prev_notice))

        # Open the notice file
        notice_file = find_file(file_name, is_notice=True)
        with open(notice_file, 'r') as f:
            notice_string = f.read()
        parser = etree.XMLParser(huge_tree=True)

        notice_xml = etree.fromstring(notice_string, parser)

        # TODO: Validate labels for json-compliance?
        # Example: JSON fails on upload only for interpParagraphs without "Interp" in them

        # Validate the files
        regulation_validator = get_validator(prev_tree)
        terms_layer = build_terms_layer(prev_tree)

        try:
            notice_validator = get_validator(notice_xml, raise_instead_of_exiting=True)
        except Exception as e:
            print("[{}]".format(kk),
                  colored("Exception occurred in notice", 'red'),
                  colored(doc_number, attrs=['bold']),
                  colored("; details are below. ", 'red'),
                  "To retry this single notice, use:\n\n",
                  colored("> ./regml.py apply-notice {0}/{1} {0}/{2}\n".format(cfr_part,
                                                                               prev_notice,
                                                                               doc_number),
                          attrs=['bold']))
            sys.exit(0)

        # validate the notice XML with the layers derived from the
        # tree of the previous version
        reload_notice = False
        skip_notices = list(skip_fix_notices)

        if skip_fix_notices_through is not None:
            if skip_fix_notices_through in possible_notices:
                last_fix_idx = possible_notices.index(skip_fix_notices_through)
                skip_notices.extend(possible_notices[:last_fix_idx + 1])

        if fix_notices and doc_number not in skip_notices:
            print('Fixing notice number {}:'.format(doc_number))
            notice_validator.validate_terms(notice_xml, terms_layer)
            notice_validator.validate_term_references(notice_xml, terms_layer, notice_file)
            notice_terms_layer = build_terms_layer(notice_xml)
            notice_validator.validate_term_references(notice_xml, notice_terms_layer, notice_file)
            notice_validator.fix_omitted_cites(notice_xml, notice_file)
            reload_notice = True

        # at this point the file has possibly changed, so we should really reload it
        if reload_notice:
            with open(notice_file, 'r') as f:
                notice_string = f.read()
            parser = etree.XMLParser(huge_tree=True)

            notice_xml = etree.fromstring(notice_string, parser)

        # Process the notice changeset
        try:
            new_xml_tree = process_changes(prev_tree, notice_xml)
        except Exception as e:
            print("[{}]".format(kk),
                  colored("Exception occurred; details are below. ".format(kk), 'red'),
                  "To retry this single notice, use:\n\n",
                  colored("> ./regml.py apply-notice {0}/{1} {0}/{2}\n".format(cfr_part,
                                                                               prev_notice,
                                                                               doc_number),
                          attrs=['bold']))
            raise e

        # Add in any new analysis
        new_xml_tree = process_analysis(new_xml_tree, notice_xml)

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
    parser = etree.XMLParser(huge_tree=True)
    notice_xml = etree.fromstring(notice_string, parser)
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
    parser = etree.XMLParser(huge_tree=True)
    left_xml_tree = etree.fromstring(left_reg_xml, parser)

    prev_notice = version
    prev_tree = left_xml_tree
    for notice in notices:
        print('Applying notice {} to version {}'.format(notice, prev_notice))
        notice_file = find_file(os.path.join(cfr_part, notice), is_notice=True)
        with open(notice_file, 'r') as f:
            notice_string = f.read()
        parser = etree.XMLParser(huge_tree=True)
        notice_xml = etree.fromstring(notice_string, parser)

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
    regml_notice_files = find_all(part, is_notice=True)
    print(colored("RegML Notices are available for:", attrs=['bold']))
    regml_notices = []
    for notice_file in regml_notice_files:
        with open(os.path.join(notice_file), 'r') as f:
            notice_xml = f.read()
        parser = etree.XMLParser(huge_tree=True)
        xml_tree = etree.fromstring(notice_xml, parser)
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

# Create a general ecfr group that can take additional commands
@cli.group()
def ecfr():
    pass

# Wrap the eCFR parser as a library for the purposes of our workflow.
# This is equivalent to build_from.py
@ecfr.command('parse-all')
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
@click.option('--checkpoints',
              help="path to store/retrieve ecfr parser checkpoints")
def ecfr_all(title, file, act_title, act_section,
             with_all_versions=False, without_versions=False,
             without_notices=False, only_notice=None, checkpoints=None):
    """ Parse eCFR into RegML """

    # Get the tree and layers
    reg_tree, builder = tree_and_builder(
        file, title, checkpoints, writer_type='XML')
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


@ecfr.command('parse-notice')
@click.argument('title', type=int)
@click.argument('cfr_part')
@click.argument('notice')
@click.option('--applies-to',
              help="document number to which the new notice applies")
@click.option('--act-section', default=0, type=int)
@click.option('--act-title', default=0, type=int)
@click.option('--with-version', is_flag=True,
              help="output the full reg tree version")
@click.option('--without-notice', is_flag=True,
              help="output the notice changeset")
def ecfr_notice(title, cfr_part, notice, applies_to, act_title,
                act_section, with_version=False, without_notice=False):
    """ Generate RegML for a single notice from eCFR XML. """

    # Get the notice the new one applies to
    with open(find_file(os.path.join(cfr_part, applies_to)), 'r') as f:
        reg_xml = f.read()
    parser = etree.XMLParser(huge_tree=True)
    xml_tree = etree.fromstring(reg_xml, parser)
    doc_number = xml_tree.find('.//{eregs}documentNumber').text

    # Validate the file relative to schema
    validator = get_validator(xml_tree)

    # Get the ecfr builder
    builder = Builder(cfr_title=title,
                      cfr_part=cfr_part,
                      doc_number=doc_number,
                      checkpointer=None,
                      writer_type='XML')

    # Fetch the notices from the FR API and find the notice we're
    # looking for
    builder.fetch_notices_json()
    print([n['document_number'] for n in builder.notices_json])
    notice_json = next((n for n in builder.notices_json
                        if n['document_number'] == notice))

    # Build the notice
    notice = builder.build_single_notice(notice_json)[0]

    if 'changes' not in notice:
        print('There are no changes in this notice to apply.')
        return

    # We've successfully fetched and parsed the new notice.
    # Build a the reg tree and layers for the notice it applies to.
    old_tree = build_reg_tree(xml_tree)

    # Build the new reg tree from the old_tree + notice changes
    last_version = doc_number
    version = notice['document_number']
    merged_changes = builder.merge_changes(version, notice['changes'])
    reg_tree = compile_regulation(old_tree, merged_changes)
    layer_cache = LayerCacheAggregator()
    layers = builder.generate_layers(reg_tree,
                                     [act_title, act_section],
                                     layer_cache)

    # Write the notice file
    if not without_notice:
        builder.write_notice(version,
                             old_tree=old_tree,
                             reg_tree=reg_tree,
                             layers=layers,
                             last_version=last_version)

    # Write the regulation file for the new notice
    if with_version:
        builder.write_regulation(new_tree, layers=layers)


@ecfr.command('analysis')
@click.argument('ecfr_file')
@click.argument('regml_file')
def ecfr_analysis(ecfr_file, regml_file):
    """ Extract analysis from eCFR XML using using XSL

        This is a blunt-force attempt to extract SxS analysis from an
        eCFR XML file and force it into RegML using XSL
        (utils/ecfr_sxs_to_regml.xsl).

        The result will very likely have to be hand-edited before it
        will work as intended. """

    # Get the ecfr xml
    with open(ecfr_file, 'r') as f:
        ecfr_xml = f.read()
    parser = etree.XMLParser(huge_tree=True, remove_blank_text=True)
    ecfr_tree = etree.fromstring(ecfr_xml, parser)

    # Get the regml
    with open(regml_file, 'r') as f:
        reg_xml = f.read()
    parser = etree.XMLParser(huge_tree=True, remove_blank_text=True)
    regml_tree = etree.fromstring(reg_xml, parser)
    doc_number = regml_tree.find('.//{eregs}documentNumber').text
    date = regml_tree.find('.//{eregs}effectiveDate').text

    # Get the XSL file
    xsl_file = os.path.join(os.path.dirname(__file__), 'utils', 'ecfr_sxs_to_regml.xsl')
    with open(xsl_file, 'r') as f:
        xslt_xml = f.read()
    parser = etree.XMLParser(huge_tree=True, remove_blank_text=True)
    xslt_tree = etree.fromstring(xslt_xml, parser)
    sxs_transform = etree.XSLT(xslt_tree)

    # Now that we have all the files, try to find the section-by-section
    # analysis in the eCFR file. It should be between two HD1 with
    # "Section-by-Section Analysis" in the text.
    hd1_elms = ecfr_tree.findall('.//HD[@SOURCE="HD1"]')
    try:
        hd1_sxs = next((e for e in hd1_elms
                        if 'Section-by-Section Analysis' in e.text))
    except StopIteration:
        print(colored('No section-by-section analysis found', 'red'))
        return
    print(colored('Found section-by-section header', 'green'))

    hd1_next = hd1_elms[hd1_elms.index(hd1_sxs)+1]

    # The SxS is everything between those two HD1s
    sxs_parent = hd1_sxs.getparent()
    sxs_body = sxs_parent[sxs_parent.index(hd1_sxs):sxs_parent.index(hd1_next)]

    if len(sxs_body) == 0:
        print(colored('No section-by-section analysis found', 'red'))
        return
    print(colored('Found analysis', 'green'))

    for elm in sxs_body:
        if elm.tag == "HD" and elm.get('SOURCE') == 'HD2':
            print(colored('\t' + elm.text, 'green'))

    # Create a dummy root element that we can apply the xslt to
    sxs_dummy = etree.Element("sxs")
    sxs_dummy.extend(sxs_body)
    result_tree = sxs_transform(sxs_dummy).getroot()
    print(colored('Transformed analysis', 'green'))

    # Add the resulting tree to the regml... if analysis already exists,
    # append the analysisSections to the end.
    existing_analysis = regml_tree.find('.//{eregs}analysis')
    if existing_analysis is not None:
        print(colored('Existing analysis found, adding analysis from eCFR',
                      'yellow'))
        print(colored('WARNING: There may be duplication that results.',
                      'yellow'))
        existing_analysis.append(etree.Comment("Added analysis from eCFR"))
        for section_elm in result_tree:
            existing_analysis.append(section_elm)

    else:
        print(colored('Adding analysis to RegML', 'green'))
        regml_tree.append(result_tree)

    # Write the regml tree
    regml_string = etree.tostring(regml_tree,
                                  pretty_print=True,
                                  xml_declaration=True,
                                  encoding='UTF-8')
    with open(regml_file, 'w') as f:
        f.write(regml_string)

    # Remind the user that hand-editing to add the appropriate
    # attributes and structure is *required*
    print(colored('Saved analysis in {}'.format(regml_file),
                  'green', attrs=['bold']))

    print(colored('REMINDER: the analysis will require hand-editing to '
                  'ensure correct structure.', 'yellow', attrs=['bold']))
    print(colored('REMINDER: top-level analysisSections will need the '
                  'following attributes added:', 'yellow', attrs=['bold']))
    print(colored('    target="THE TARGET" notice="{}" date="{}"'.format(
                  doc_number, date), attrs=['bold']))

@cli.command('gui')
def run_gui():

    import Tkinter as tk
    from ui.main import EregsApp

    root = tk.Tk()
    root.title('Eregs')
    root.geometry("1280x1024+300+300")
    app = EregsApp(root)
    root.mainloop()


if __name__ == "__main__":
    cli()
