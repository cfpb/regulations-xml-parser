__author__ = 'vinokurovy'

from regulation.node import *

import re

import pdb


def build_reg_tree(root, parent=None):

    ns_prefix = '{eregs}'
    tag = root.tag.replace(ns_prefix, '')
    node = RegNode(include_children=True)

    if tag == 'regulation':
        preamble = root.find(ns_prefix + 'preamble')
        section = preamble.find('{eregs}cfr/{eregs}section').text
        fdsys = root.find(ns_prefix + 'fdsys')
        title = fdsys.find(ns_prefix + 'title').text

        node.label = [section]
        node.marker = None
        node.node_type = 'regtext'
        node.title = title

        subparts = root.findall('.//{eregs}subpart')
        appendices = root.findall('.//{eregs}appendix')

        children = subparts + appendices

    elif tag == 'subpart':
        title = root.find(ns_prefix + 'title')
        if title:
            node.node_type == 'subpart'
            node.title = title.text
            node.label = parent.label + ['Subpart', root.get('subpartLetter')]
        else:
            node.node_type == 'emptypart'
            node.title = ''
            node.label = parent.label + ['Subpart']

        node.text = ''

        content = root.find('{eregs}content')
        children = content.findall('{eregs}section')

    elif tag == 'section' and root.attrib != {}:
        subject = root.find(ns_prefix + 'subject')
        # print root, parent.node_type, subject.text
        label = root.get('label').split('-')
        node.title = subject.text
        node.node_type = 'regtext'
        node.label = label

        children = root.findall('{eregs}paragraph')

    elif tag == 'paragraph':

        title = root.find('{eregs}title')
        content = root.find('{eregs}content')
        content_text = xml_node_text(content)
        if title is not None:
            node.title = title.text
        node.marker = root.get('marker')
        node.label = root.get('label').split('-')
        # node.text = content_text
        node.text = '{} {}'.format(root.get('marker'), content_text)
        node.node_type = parent.node_type
        node.mixed_text = xml_mixed_text(content)

        children = root.findall('{eregs}paragraph')

    elif tag == 'appendix':

        title = root.find('{eregs}appendixTitle')
        label = root.get('label').split('-')
        node.node_type = 'appendix'
        node.text = ''
        node.title = title.text
        node.label = label

        children = root.findall('{eregs}appendixSection')

    elif tag == 'appendixSection':

        subject = root.find('{eregs}subject')
        label = root.get('label').split('-')
        node.node_type = 'appendix'
        node.text = ''
        node.title = subject.text
        node.label = label

        children = root.findall('{eregs}paragraph')

    else:
        children = []

    for child in children:
        node.children.append(build_reg_tree(child, parent=node))

    return node


def build_paragraph_marker_layer(root):

    parapgraphs = root.findall('.//{eregs}paragraph')
    paragraph_dict = OrderedDict()

    for paragraph in parapgraphs:

        marker = paragraph.get('marker')
        label = paragraph.get('label')
        if marker != '':
            marker_dict = {'locations': [0],
                           'text': marker}
            paragraph_dict[label] = [marker_dict]

    return paragraph_dict


def build_internal_citations_layer(root):

    paragraphs = root.findall('.//{eregs}paragraph')
    layer_dict = OrderedDict()

    for paragraph in paragraphs:
        marker = paragraph.get('marker')
        par_text = marker + ' ' + xml_node_text(paragraph.find('{eregs}content'))
        par_label = paragraph.get('label')
        cites = paragraph.findall('.//{eregs}ref[@reftype="internal"]')
        citation_list = []
        for cite in cites:
            target = cite.get('target').split('-')
            text = cite.text
            positions = find_all_occurrences(par_text, text)
            for pos in positions:
                cite_dict = {'citation': target,
                             'offsets': [[pos, pos + len(text)]]}
                if cite_dict not in citation_list:
                    citation_list.append(cite_dict)

        if citation_list != []:
            layer_dict[par_label] = citation_list

    return layer_dict


def build_external_citations_layer(root):

    paragraphs = root.findall('.//{eregs}paragraph')
    layer_dict = OrderedDict()

    for paragraph in paragraphs:
        marker = paragraph.get('marker')
        par_text = marker + ' ' + xml_node_text(paragraph.find('{eregs}content'))
        par_label = paragraph.get('label')
        cites = paragraph.findall('.//{eregs}ref[@reftype="external"]')
        citation_list = []
        for cite in cites:
            target = cite.get('target').split(':')
            citation_type = target[0]
            citation_target = target[1].split('-')
            text = cite.text
            positions = find_all_occurrences(par_text, text)
            cite_dict = OrderedDict()
            cite_dict['citation'] = citation_target
            cite_dict['citation_type'] = citation_type
            cite_dict['offsets'] = []
            for pos in positions:
                cite_dict['offsets'].append([pos, pos + len(text)])

            if cite_dict not in citation_list and cite_dict['offsets'] != []:
                citation_list.append(cite_dict)

        if citation_list != []:
            layer_dict[par_label] = citation_list

    return layer_dict


def build_terms_layer(root):

    definitions_dict = OrderedDict()
    terms_dict = OrderedDict()

    paragraphs = root.findall('.//{eregs}paragraph')

    for paragraph in paragraphs:
        content = paragraph.find('{eregs}content')
        terms = content.findall('.//{eregs}ref[@reftype="term"]')
        label = paragraph.get('label')
        marker = paragraph.get('marker')
        par_text = marker + ' ' + xml_node_text(paragraph.find('{eregs}content'))
        targets = []
        if len(terms) > 0:
            terms_dict[label] = []
        for term in terms:
            text = term.text
            target = text + ':' + term.get('target')
            # if term.get('target') not in targets:
            # targets.append(term.get('target'))
            positions = find_all_occurrences(par_text, text)
            ref_dict = OrderedDict()
            ref_dict['offsets'] = []
            for pos in positions:
                ref_dict['offsets'].append([pos, pos + len(text)])
            ref_dict['ref'] = target
            if len(ref_dict['offsets']) > 0 and ref_dict not in terms_dict[label]:
                terms_dict[label].append(ref_dict)

        definitions = paragraph.findall('.//{eregs}def')
        for defn in definitions:
            defined_term = defn.get('term')
            key = defined_term + ':' + label
            def_text = defn.text
            positions = find_all_occurrences(par_text, def_text)
            def_dict = OrderedDict()
            #def_dict['offsets'] = []
            #for pos in positions:
            pos = positions[0]
            def_dict['position'] = [pos, pos + len(def_text)]
            def_dict['reference'] = label
            def_dict['term'] = defined_term
            if def_dict['position'] != []:
                definitions_dict[key] = def_dict

    terms_dict['referenced'] = definitions_dict

    return terms_dict


def build_meta_layer(root):

    meta_dict = OrderedDict()

    part_to_letter = {'1001': 'A', '1002': 'B', '1003': 'C',
                      '1004': 'D', '1005': 'E', '1006': 'F',
                      '1007': 'G', '1008': 'H', '1009': 'I',
                      '1010': 'J', '1011': 'K', '1012': 'L',
                      '1013': 'M', '1014': 'N', '1015': 'O',
                      '1016': 'P', '1017': 'Q', '1018': 'R',
                      '1019': 'S', '1020': 'T', '1021': 'U',
                      '1022': 'V', '1023': 'W', '1024': 'X',
                      '1025': 'Y', '1026': 'Z'}

    preamble = root.find('{eregs}preambe')
    fdsys = root.find('{eregs}fdsys')
    eff_date = preamble.find('{eregs}effectiveDate').text
    cfr_title_num = fdsys.find('{eregs}cfrTitleNum').text
    cfr_title_text = fdsys.find('{eregs}cfrTitleText').text
    statutory_name = fdsys.find('{eregs}title').text
    part = preamble.find('{eregs}cfr').find('{eregs}section').text

    part_letter = part_to_letter[part]

    meta_dict[part] = [
        {
            'cfr_title_number': cfr_title_num,
            'cfr_title_text': cfr_title_text,
            'effective_date': eff_date,
            'reg_letter': part_letter,
            'statutory_name': statutory_name
        }
    ]

    return meta_dict


def build_formatting_layer(root):

    formatting_dict = OrderedDict