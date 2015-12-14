# -*- coding: utf-8 -*-

from collections import OrderedDict

import inflect

from regulation.node import (RegNode, xml_node_text, xml_mixed_text,
                             find_all_occurrences, enclosed_in_tag)
import settings

from lxml import etree


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
        interpretations = root.findall('.//{eregs}interpretations')

        children = subparts + appendices + interpretations

    elif tag == 'subpart':
        title = root.find(ns_prefix + 'title')
        if title is not None:
            node.node_type = 'subpart'
            node.title = title.text
            node.label = parent.label + ['Subpart', root.get('subpartLetter')]
        else:
            node.node_type = 'emptypart'
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
        if title is not None and title.get('type') != 'keyterm':
            node.title = title.text
        node.marker = root.get('marker')
        if node.marker == 'none':
            marker = ''
        else:
            marker = node.marker
        node.label = root.get('label').split('-')

        graphic = content.find('{eregs}graphic')
        if graphic is not None:
            node.text = graphic.find('{eregs}text').text
        else:
            node.text = '{} {}'.format(marker, content_text).strip()
        node.node_type = parent.node_type
        # node.mixed_text = xml_mixed_text(content)

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

    elif tag == 'interpretations':

        title = root.find('{eregs}title')
        label = root.get('label').split('-')
        node.node_type = 'interp'
        node.text = ''
        node.title = title.text
        node.label = label

        children = root.findall('{eregs}interpSection')

    elif tag == 'interpSection':

        title = root.find('{eregs}title')
        label = root.get('label').split('-')
        node.node_type = 'interp'
        node.text = ''
        node.title = title.text
        node.label = label

        children = root.findall('{eregs}interpParagraph')

    elif tag == 'interpParagraph':

        title = root.find('{eregs}title')
        content = root.find('{eregs}content')
        content_text = xml_node_text(content)
        if title is not None:
            node.title = title.text
        node.label = root.get('label').split('-')
        node.text = content_text
        node.node_type = 'interp'

        children = root.findall('{eregs}interpParagraph')

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

    paragraphs = root.findall('.//{eregs}paragraph') + root.findall('.//{eregs}interpParagraph')
    layer_dict = OrderedDict()

    for paragraph in paragraphs:
        marker = paragraph.get('marker', '')
        if marker == 'none' or marker is None:
            marker = ''
        par_text = (marker + ' ' + xml_node_text(
            paragraph.find('{eregs}content'))).strip()

        par_label = paragraph.get('label')

        if marker != '':
            marker_offset = len(marker + ' ')
        else:
            marker_offset = 0

        cite_positions = OrderedDict()
        cite_targets = OrderedDict()

        content = paragraph.find('{eregs}content')
        cites = content.findall('{eregs}ref[@reftype="internal"]')
        citation_list = []
        for cite in cites:
            # import pdb
            # pdb.set_trace()

            target = cite.get('target').split('-')
            text = cite.text

            running_par_text = content.text or ''
            for child in content.getchildren():
                if child != cite:
                    running_par_text += child.text + child.tail
                else:
                    break

            cite_position = len(running_par_text) + marker_offset
            cite_positions.setdefault(text, []).append(cite_position)
            cite_targets[text] = target
            running_par_text = ''

        for cite, positions in cite_positions.iteritems():
            # positions = find_all_occurrences(par_text, text)
            for pos in positions:
                cite_dict = {'citation': cite_targets[cite],
                             'offsets': [[pos, pos + len(cite)]]}
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
        par_text = marker + ' ' + xml_node_text(
            paragraph.find('{eregs}content'))
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


def build_graphics_layer(root):

    layer_dict = OrderedDict()
    paragraphs = root.findall('.//{eregs}paragraph')

    for paragraph in paragraphs:
        content = paragraph.find('{eregs}content')
        graphics = content.findall('{eregs}graphic')
        label = paragraph.get('label')
        if len(graphics) > 0:
            layer_dict[label] = []
        for graphic in graphics:
            text = graphic.find('{eregs}text').text
            alt_text = graphic.find('{eregs}altText').text
            if alt_text is None:
                alt_text = ''
            url = graphic.find('{eregs}url').text
            graphic_dict = OrderedDict()
            graphic_dict['alt'] = alt_text
            graphic_dict['locations'] = [0]
            graphic_dict['text'] = text
            graphic_dict['url'] = url

            layer_dict[label].append(graphic_dict)

    return layer_dict


def build_formatting_layer(root):

    layer_dict = OrderedDict()
    paragraphs = root.findall('.//{eregs}paragraph')

    for paragraph in paragraphs:
        content = paragraph.find('{eregs}content')
        dashes = content.findall('.//{eregs}dash')
        tables = content.findall('.//{eregs}table')
        label = paragraph.get('label')
        if len(dashes) > 0:
            layer_dict[label] = []
            for dash in dashes:
                dash_dict = OrderedDict()
                dash_text = dash.text
                if dash_text is None:
                    dash_text = ''
                dash_dict['text'] = dash_text + 5 * '_'
                dash_dict['dash_data'] = {'text': dash_text}
                dash_dict['locations'] = [0]
                layer_dict[label].append(dash_dict)
        if len(tables) > 0:
            if label not in layer_dict:
                layer_dict[label] = []
            for table in tables:
                table_md = '|'
                table_dict = OrderedDict()
                table_data_dict = OrderedDict()
                table_data_dict['header'] = []
                table_data_dict['rows'] = []
                table_dict['locations'] = [0]
                header = table.find('{eregs}header')
                header_rows = header.findall('{eregs}columnHeaderRow')
                for column_header in header_rows:
                    columns = column_header.findall('{eregs}column')
                    column_arr = []
                    for column in columns:
                        column_header_dict = OrderedDict()
                        column_header_dict['colspan'] = int(
                            column.get('colspan'))
                        column_header_dict['rowspan'] = int(
                            column.get('rowspan'))
                        column_text = column.text
                        if column_text is None:
                            column_text = ''
                        column_header_dict['text'] = column_text
                        table_md += column_text + '|'
                        column_arr.append(column_header_dict)
                    table_data_dict['header'].append(column_arr)
                    table_md += '\n|'

                data_rows = table.findall('{eregs}row')
                for i, row in enumerate(data_rows):
                    row_arr = []
                    cells = row.findall('{eregs}cell')
                    for cell in cells:
                        cell_text = cell.text
                        if cell_text is None:
                            cell_text = ''
                        row_arr.append(cell_text)
                        table_md += cell_text + '|'
                    table_data_dict['rows'].append(row_arr)
                    if i < len(data_rows) - 1:
                        table_md += '\n|'
                table_dict['table_data'] = table_data_dict
                table_dict['text'] = ''
                layer_dict[label].append(table_dict)

    return layer_dict


def build_terms_layer(root):

    definitions_dict = OrderedDict()
    terms_dict = OrderedDict()

    inf_engine = inflect.engine()
    inf_engine.defnoun('bonus', 'bonuses')

    paragraphs = root.findall('.//{eregs}paragraph') + \
        root.findall('.//{eregs}interpParagraph')

    for paragraph in paragraphs:
        content = paragraph.find('{eregs}content')
        terms = content.findall('.//{eregs}ref[@reftype="term"]')
        # terms = sorted(terms, key=lambda term: len(term.text), reverse=True)
        label = paragraph.get('label')

        marker = paragraph.get('marker') or ''

        par_text = (marker + ' ' + xml_node_text(content).strip())

        if len(terms) > 0:
            terms_dict[label] = []

        if marker != '':
            marker_offset = len(marker + ' ')
        else:
            marker_offset = 0
        term_positions = OrderedDict()
        term_targets = OrderedDict()

        for term in terms:
            running_par_text = content.text or ''
            for child in content.getchildren():
                if child != term:
                    running_par_text += child.text + child.tail
                else:
                    break

            text = term.text
            if inf_engine.singular_noun(text.lower()) and \
                    not text.lower() in settings.SPECIAL_SINGULAR_NOUNS:
                target = inf_engine.singular_noun(text.lower()) + ':' + \
                    term.get('target')
            else:
                target = text.lower() + ':' + term.get('target')

            term_position = len(running_par_text) + marker_offset
            term_positions.setdefault(text, []).append(term_position)
            term_targets[text] = target

        for term, positions in term_positions.iteritems():
            target = term_targets[term]
            ref_dict = OrderedDict()
            ref_dict['offsets'] = []
            for pos in positions:
                ref_dict['offsets'].append([pos, pos + len(term)])
            ref_dict['ref'] = target
            if len(ref_dict['offsets']) > 0 and \
                    ref_dict not in terms_dict[label]:
                terms_dict[label].append(ref_dict)

        definitions = paragraph.find('{eregs}content').findall('{eregs}def')
        for defn in definitions:
            defined_term = defn.get('term')
            if inf_engine.singular_noun(defined_term.lower()) and not \
                    defined_term.lower() in settings.SPECIAL_SINGULAR_NOUNS:
                key = inf_engine.singular_noun(defined_term.lower()) + \
                    ':' + label
            else:
                key = defined_term.lower() + ':' + label
            # key = inf_engine.singular_noun(defined_term.lower()) + ':' +label
            def_text = defn.text
            positions = find_all_occurrences(par_text, def_text)
            def_dict = OrderedDict()
            # def_dict['offsets'] = []
            # for pos in positions:
            pos = positions[0]
            def_dict['position'] = [pos, pos + len(def_text)]
            def_dict['reference'] = label
            def_dict['term'] = defined_term
            if def_dict['position'] != []:
                definitions_dict[key] = def_dict

    terms_dict['referenced'] = definitions_dict

    return terms_dict


def build_toc_layer(root):

    toc_dict = OrderedDict()

    part = root.find('{eregs}part')
    part_toc = part.find('{eregs}tableOfContents')
    part_number = part.get('partNumber')
    toc_dict[part_number] = []
    appendix_letters = []

    for section in part_toc.findall('{eregs}tocSecEntry'):
        target = section.get('target').split('-')
        subject = section.find('{eregs}sectionSubject').text
        toc_entry = {'index': target, 'title': subject}
        toc_dict[part_number].append(toc_entry)

    for appendix_section in part_toc.findall('{eregs}tocAppEntry'):
        target = appendix_section.get('target').split('-')
        subject = appendix_section.find('{eregs}appendixSubject').text
        toc_entry = {'index': target, 'title': subject}
        toc_dict[part_number].append(toc_entry)

    subparts = part.find('{eregs}content').findall('{eregs}subpart')
    for subpart in subparts:
        subpart_letter = subpart.get('subpartLetter')
        if subpart_letter is not None:
            subpart_key = part_number + '-Subpart-' + subpart_letter
        else:
            subpart_key = part_number + '-Subpart'
        toc_dict[subpart_key] = []

        subpart_toc = subpart.find('{eregs}tableOfContents')
        for section in subpart_toc.findall('{eregs}tocSecEntry'):
            target = section.get('target').split('-')
            subject = section.find('{eregs}sectionSubject').text
            toc_entry = {'index': target, 'title': subject}
            toc_dict[subpart_key].append(toc_entry)

    appendices = part.find('{eregs}content').findall('{eregs}appendix')
    for appendix in appendices:
        appendix_letter = appendix.get('appendixLetter')
        appendix_letters.append(appendix_letter)
        appendix_key = part_number + '-' + appendix_letter
        toc_dict[appendix_key] = []

        appendix_toc = appendix.find('{eregs}tableOfContents')

        if appendix_toc is not None:
            for section in appendix_toc.findall('{eregs}tocAppEntry'):
                target = section.get('target').split('-')
                subject = section.find('{eregs}appendixSubject').text
                toc_entry = {'index': target, 'title': subject}
                toc_dict[appendix_key].append(toc_entry)

    interpretations = part.find('.//{eregs}interpretations').findall('{eregs}interpSection')
    interp_key = part_number + '-Interp'
    for interp in interpretations:
        title = interp.find('{eregs}title').text
        target = interp.get('label').split('-')
        if target[-1] not in appendix_letters:
            toc_entry = {'index': target, 'title': title}
            toc_dict.setdefault(interp_key, []).append(toc_entry)

    return toc_dict


def build_keyterm_layer(root):

    keyterm_dict = OrderedDict()

    subparts = root.findall('.//{eregs}subpart')
    appendices = root.findall('.//{eregs}appendix')

    paragraph_locations = subparts + appendices

    for element in paragraph_locations:
        paragraphs = element.findall('.//{eregs}paragraph')
        for paragraph in paragraphs:
            title = paragraph.find('{eregs}title')
            if title is not None and title.get('type') == 'keyterm':
                label = paragraph.get('label')
                keyterm_dict[label] = [
                    {
                        'key_term': title.text,
                        'locations': [0]
                    }
                ]

    return keyterm_dict


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
                      '1025': 'Y', '1026': 'Z', '1027': 'AA',
                      '1028': 'BB', '1029': 'CC', '1030': 'DD',
                      }

    preamble = root.find('{eregs}preamble')
    fdsys = root.find('{eregs}fdsys')
    eff_date = preamble.find('{eregs}effectiveDate').text
    cfr_title_num = int(fdsys.find('{eregs}cfrTitleNum').text)
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


def build_interp_layer(root):

    layer_dict = OrderedDict()
    interpretations = root.find('.//{eregs}interpretations')

    if interpretations is not None:
        first_label = interpretations.get('label')
        first_key = first_label.split('-')[0]
        layer_dict[first_key] = [{'reference': first_label}]
        interp_paragraphs = interpretations.findall(
            './/{eregs}interpParagraph')
        for paragraph in interp_paragraphs:
            target = paragraph.get('target')
            if target:
                label = paragraph.get('label')
                layer_dict[target] = [{'reference': label}]

    return layer_dict


def build_analysis(root):
    """
    Build the analysis layer from the given root node. This looks for
    all `analysis` elements and creates references to them.

    The actual analysis is captured in the `build_notice` function
    below.
    """
    analysis_dict = OrderedDict()

    # Find all analysis elements within the regulation
    analyses = root.findall('.//{eregs}analysis')

    # Get regulation date and document number for the analysis reference
    publication_date = root.find('.//{eregs}fdsys/{eregs}date').text
    document_number = root.find('.//{eregs}documentNumber').text

    for analysis_elm in analyses:
        # Fetch the parent's label
        label = analysis_elm.xpath('../@label')[0]

        # Labels might have multiple analysis refs. If it's not already
        # in the analyses_dict, add it.
        if label not in analysis_dict:
            analysis_dict[label] = []

        analysis_dict[label].append({
            'publication_date': (publication_date),
            'reference': (document_number, label),
        })

    return analysis_dict


def build_notice(root):
    """
    Build the notice dictioanry from the given root node.

    Notices currently contain analysis and footnotes
    """
    # Get the root label
    label = root.find('.//{eregs}part').attrib['partNumber']

    # Get regulation dates, document number, and url for the notice
    publication_date = root.find('.//{eregs}fdsys/{eregs}date').text
    document_number = root.find('.//{eregs}documentNumber').text
    effective_date = root.find('.//{eregs}effectiveDate').text
    fr_url = root.find('.//{eregs}federalRegisterURL').text

    notice_dict = OrderedDict([
        ('cfr_parts', [label, ]),
        ('effective_on', effective_date),
        ('publication_date', publication_date),
        ('fr_url', fr_url),
        ('document_number', document_number),
        ('section_by_section', []),
        ('footnotes', {})
    ])

    # Analyses
    analyses = root.findall('.//{eregs}analysis')

    def build_analysis_dict(child_elm):
        """ Recursively build a dictionary for the given analysis
            section """

        # Final list of paragraphs in this analysis section
        paragraphs = []

        # Final list of footnote references in this analysis section
        footnote_refs = []

        # Paragraphs can contain inline footnote elms. We have to
        # assemble the paragraph text from the initial paragraph's text
        # and any footnote's tails
        paragraph_elms = child_elm.findall('{eregs}analysisParagraph')
        for paragraph_elm in paragraph_elms:
            # Get the initial bit of text
            paragraph_text = paragraph_elm.text \
                if paragraph_elm.text is not None \
                else ''

            # Loop over any children and get the text from their tails.
            # If the child is a footnote, capture its reference.
            for p_child_elm in paragraph_elm.getchildren():
                if p_child_elm.tag == '{eregs}footnote':
                    footnote_refs.append({
                        'offset': len(paragraph_text),
                        'paragraph': len(paragraphs),
                        'reference': p_child_elm.attrib['ref']
                    })

                # Append the footnote 'tail' to the paragraph text
                paragraph_text += p_child_elm.tail

            # Append the full text to the list of paragraphs
            paragraphs.append(paragraph_text)

        # Grab the title
        title = child_elm.find('{eregs}title').text

        # Recruse through child analysis sections
        children = [build_analysis_dict(c)
                    for c in child_elm.findall('{eregs}analysisSection')]

        # Build the dict from all our pieces
        analysis_dict = {
            'title': title,
            'paragraphs': paragraphs,
            'footnote_refs': footnote_refs,
            'children': children,
        }

        return analysis_dict

    for analysis_elm in analyses:
        section_elm = analysis_elm.find('{eregs}analysisSection')
        analysis_dict = build_analysis_dict(section_elm)

        # Add the parent's label to the top-level of the dict
        analysis_dict['labels'] = analysis_elm.xpath('../@label')

        # Add the analysis to the notice
        notice_dict['section_by_section'].append(analysis_dict)

    # Footnotes
    footnotes = root.findall('.//{eregs}footnote')
    for footnote_elm in footnotes:
        ref = footnote_elm.attrib['ref']
        notice_dict['footnotes'][ref] = footnote_elm.text

    return notice_dict
