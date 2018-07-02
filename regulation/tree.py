# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from __future__ import print_function

from copy import deepcopy
from collections import OrderedDict
import string

import inflect

from regulation.node import (RegNode, xml_node_text, xml_mixed_text,
                             find_all_occurrences, enclosed_in_tag)
import settings

from lxml import etree


# This array contains tag types that can exist in a paragraph
# that are not part of paragraph text.
# E.g. tags like <ref> are part of the paragraph text.
NON_PARA_SUBELEMENT = ['{eregs}callout',
                       '{eregs}table',
                       '{eregs}graphic']

# This array contains tag types that can have introductory
# paragraphs, as reg-site often wants the first paragraph
# to be moved into the parent node's text
TAGS_WITH_INTRO_PARAS = ['{eregs}section',
                         '{eregs}appendixSection']

# reg-site treats interpParagraphs specially, so they
# should not have offsets calculated for the layers
TAGS_WITHOUT_OFFSETS = ['{eregs}interpParagraph']


def build_reg_tree(root, parent=None, depth=0):
    """
    This function builds the basic JSON regulation tree recursively from the supplied
    root element of the XML.

    :param root: The XML root. If this function is called from the outside, the root
        should be the very top of the tree, i.e. the ``<regulation>`` element.
    :type root: :class:`etree.Element`
    :param parent: The parent of the current element. None if the root is the
        ``<regulation>`` element.
    :type parent: :class:`etree.Element`
    :param depth: The depth at which the current element resides.
    :type depth: :class:`int`

    :return: The top node of the resulting tree.
    :rtype: :class:`regulation.node.RegNode`
    """

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
        label = root.get('label').split('-')
        node.title = subject.text
        node.node_type = 'regtext'
        node.label = label

        children = root.findall('{eregs}paragraph')

        # Check to see if the first child is an unmarked intro
        # paragraph. Reg-site expects those to be be the 'text' of this
        # node rather than child nodes in their own right.
        if len(children) > 0:
            first_child = children[0]
            # First_child may be an intro paragraph
            if is_intro_text(first_child):
                content = xml_node_text(first_child.find('{eregs}content'))
                node.text = content.strip()
                del children[0]

    elif tag == 'paragraph':
        title = root.find('{eregs}title')
        content = apply_formatting(root.find('{eregs}content'))
        content_text = xml_node_text(content)

        if title is not None:
            if title.get('type') != 'keyterm':
                node.title = title.text
            else:
                # Keyterms are expected by reg-site to be included in
                # the content text rather than the title of a node.
                content_text = title.text + content_text

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
        node.mixed_text = xml_mixed_text(content)
        node.source_xml = root

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

        # Check to see if the first child is an unmarked intro
        # paragraph. Reg-site expects those to be be the 'text' of this
        # node rather than child nodes in their own right.
        if len(children) > 0:
            first_child = children[0]
            # First_child may be an intro paragraph
            if is_intro_text(first_child):
                content = xml_node_text(first_child.find('{eregs}content'))
                node.text = content.strip()
                del children[0]

    elif tag == 'interpretations':

        title = root.find('{eregs}title')
        label = root.get('label').split('-')
        node.node_type = 'interp'
        node.text = ''
        node.title = title.text
        node.label = label

        children = root.findall('{eregs}interpSection')

    elif tag == 'interpSection' or tag == 'interpAppSection':

        title = root.find('{eregs}title')
        label = root.get('label').split('-')
        node.node_type = 'interp'
        node.text = ''
        node.title = title.text
        node.label = label

        children = root.findall('{eregs}interpParagraph')

    elif tag == 'interpAppendix':

        title = root.find('{eregs}title')
        label = root.get('label').split('-')
        node.node_type = 'interp'
        node.text = ''
        node.title = title.text
        node.label = label

        children = root.findall('{eregs}interpAppSection')

    elif tag == 'interpParagraph':

        title = root.find('{eregs}title')
        content = apply_formatting(root.find('{eregs}content'))
        content_text = xml_node_text(content)

        if title is not None:
            if title.get('type') != 'keyterm':
                node.title = title.text
            else:
                # Keyterms are expected by reg-site to be included in
                # the content text rather than the title of a node.
                content_text = title.text + content_text

        node.marker = root.get('marker', '')
        if node.marker == 'none':
            node.marker = ''

        node.label = root.get('label').split('-')
        node.text = content_text
        node.node_type = 'interp'
        node.source_xml = root

        children = root.findall('{eregs}interpParagraph')

    else:
        children = []

    node.depth = depth

    for child in children:
        node.children.append(build_reg_tree(child, parent=node, depth=depth+1))

    return node


def build_paragraph_marker_layer(root):
    """
    Build the paragraph marker layer from the provided root of the XML tree.

    :param root: The root element of the XML tree.
    :type root: :class:`etree.Element`

    :return: An OrderedDict containing the locations of markers, suitable for direct
        transformation into JSON for use with the eRegs frontend.
    :rtype: :class:`collections.OrderedDict`:
    """
    paragraphs = root.findall('.//{eregs}paragraph') # + root.findall('.//{eregs}interpParagraph')
    paragraph_dict = OrderedDict()

    for paragraph in paragraphs:

        marker = paragraph.get('marker')
        label = paragraph.get('label')
        if marker != '':
            marker_dict = {'locations': [0],
                           'text': marker}
            paragraph_dict[label] = [marker_dict]

    return paragraph_dict


def build_internal_citations_layer(root):
    """
    Build the internal citations layer from the provided root of the XML tree.

    :param root: The root element of the XML tree.
    :type root: :class:`etree.Element`

    :return: An OrderedDict containing the locations of internal citations, suitable for direct
        transformation into JSON for use with the eRegs frontend.
    :rtype: :class:`collections.OrderedDict`:
    """

    paragraphs = root.findall('.//{eregs}paragraph') + root.findall('.//{eregs}interpParagraph')
    layer_dict = OrderedDict()

    for paragraph in paragraphs:
        marker = paragraph.get('marker', '')
        title = paragraph.find('{eregs}title')

        if marker == 'none' or marker is None:
            marker = ''
        par_text = (marker + ' ' + xml_node_text(
            paragraph.find('{eregs}content'))).strip()

        par_label = paragraph.get('label')
        if wants_intro_text(paragraph.getparent()) and is_intro_text(paragraph):
            # This intro paragraph will get attached to its parent node by
            # build_reg_tree
            par_label = paragraph.getparent().get('label')

        total_offset = get_offset(paragraph, marker, title)

        cite_positions = OrderedDict()
        cite_targets = OrderedDict()

        content = apply_formatting(paragraph.find('{eregs}content'))
        cites = content.findall('{eregs}ref[@reftype="internal"]')
        citation_list = []
        for cite in cites:
            target = cite.get('target').split('-')
            text = cite.text

            running_par_text = content.text or ''
            for child in content.getchildren():
                if child != cite:
                    tail = child.tail or ''
                    running_par_text += (child.text or '') + tail
                else:
                    break

            cite_position = len(running_par_text) + total_offset
            cite_positions.setdefault(text, []).append(cite_position)
            cite_targets[text] = target
            running_par_text = ''

        for cite, positions in cite_positions.items():
            # positions = find_all_occurrences(par_text, text)
            for pos in positions:
                # Handle empty citations
                try:
                    cite_dict = {'citation': cite_targets[cite],
                                 'offsets': [[pos, pos + len(cite)]]}
                except TypeError as e:
                    print("TypeError occurred: {}".format(str(e)))
                    print("Look for a reference without text in {} @ pos {}".format(par_label, positions))
                    raise e

                if cite_dict not in citation_list:
                    citation_list.append(cite_dict)

        if citation_list != []:
            layer_dict[par_label] = citation_list

    return layer_dict


def build_external_citations_layer(root):
    """
    Build the external citations layer from the provided root of the XML tree.

    :param root: The root element of the XML tree.
    :type root: :class:`etree.Element`

    :return: An OrderedDict containing the locations of external citations, suitable for direct
        transformation into JSON for use with the eRegs frontend.
    :rtype: :class:`collections.OrderedDict`:
    """

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
            try:
                citation_target = target[1].split('-')
            except IndexError as e:
                print("Error in external citations: '{}' is not formatted properly. ".format(target),
                      "Look for an empty or malformed target in a reftype=\"external\".")
                raise e
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
    """
    Build the graphics layer from the provided root of the XML tree.

    :param root: The root element of the XML tree.
    :type root: :class:`etree.Element`

    :return: An OrderedDict containing the locations of markers, suitable for direct
        transformation into JSON for use with the eRegs frontend.
    :rtype: :class:`collections.OrderedDict`:
    """

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
    """
    Build the formatting layer from the provided root of the XML tree. Formatting elements include
    things like callouts, tables, lines indicating spaces on a form, and so on.

    :param root: The root element of the XML tree.
    :type root: :class:`etree.Element`

    :return: An OrderedDict containing the locations of formatting elements, suitable for direct
        transformation into JSON for use with the eRegs frontend.
    :rtype: :class:`collections.OrderedDict`:
    """

    layer_dict = OrderedDict()
    paragraphs = root.findall('.//{eregs}paragraph') + \
        root.findall('.//{eregs}interpParagraph')

    for paragraph in paragraphs:
        content = paragraph.find('{eregs}content')
        dashes = content.findall('.//{eregs}dash')
        tables = content.findall('.//{eregs}table')
        variables = content.findall('.//{eregs}variable')
        callouts = content.findall('.//{eregs}callout')
        label = paragraph.get('label')

        if len(dashes) > 0:
            layer_dict[label] = []
            for dash in dashes:
                dash_dict = OrderedDict()
                dash_text = dash.text
                if dash_text is None:
                    dash_text = ''
                dash_dict['dash_data'] = {'text': dash_text}
                dash_dict['locations'] = [0]
                dash_dict['text'] = dash_text + '_____'
                layer_dict[label].append(dash_dict)

        if len(variables) > 0:
            if label not in layer_dict:
                layer_dict[label] = []

            for variable in variables:
                subscript = variable.find('{eregs}subscript')
                var_dict = OrderedDict()
                var_dict['subscript_data'] = {
                    'variable': variable.text,
                    'subscript': subscript.text,
                }
                var_dict['locations'] = [0]
                var_dict['text'] = '{var}_{{{sub}}}'.format(
                        var=variable.text, sub=subscript.text)
                layer_dict[label].append(var_dict)

        if len(callouts) > 0:
            if label not in layer_dict:
                layer_dict[label] = []

            for callout in callouts:
                lines = callout.findall('{eregs}line')
                callout_dict = OrderedDict()
                callout_dict['fence_data'] = {
                    'lines': [l.text for l in lines],
                    'type': callout.get('type')
                }
                callout_dict['locations'] = [0]
                if callout.get('type') == 'note':
                    callout_dict['text'] = xml_node_text(callout).strip()
                elif callout.get('type') == 'code':
                    callout_dict['text'] = '```\n' + \
                        '\n'.join([l.text for l in lines]) + \
                        '```'
                layer_dict[label].append(callout_dict)

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


def apply_formatting(content_elm):
    """
    Applies special inline formatting to variables and callouts, as expected by
    the frontend formatting layer.

    :param content_elm: The ``<content>`` element to which the inline formatting is to be applied.
    :type content_elm: :class:`etree.Element`

    :return: the element with the inline formatting applied.
    :rtype: :class:`etree.Element`:
    """

    working_content = deepcopy(content_elm)

    # Before building the content text, replace any variable
    # elements with Var_{sub} so that reg-site will know what to
    # do with them.
    variables = working_content.findall('{eregs}variable') or []
    for variable in variables:
        # Note: lxml/etree API makes this a lot harder than it
        # should be by use text/tail instead of text nodes.
        subscript = variable.find('{eregs}subscript')
        replacement_text = '{var}_{{{sub}}}'.format(
            var=variable.text, sub=subscript.text)
        if variable.tail is not None:
            replacement_text += variable.tail

        # If there's a previous node, simply append the text to its
        # tail.
        if variable.getprevious() is not None:
            previous = variable.getprevious()
            if previous.tail is None:
                previous.tail = ''
            previous.tail += replacement_text

        # Otherwise, operate on the parent
        else:
            v_parent = variable.getparent()
            if v_parent.text is None:
                v_parent.text = ''
            v_parent.text += replacement_text

        # Remove the variable node
        variable.getparent().remove(variable)

    # Do the same for callouts
    callouts = working_content.findall('.//{eregs}callout')
    for callout in callouts:
        lines = callout.findall('{eregs}line')
        callout_text = xml_node_text(callout).strip()
        # Callouts *should* be the only things within the content
        # element of a paragraph. Assume that.
        callout.getparent().remove(callout)
        if callout.get('type') == 'note':
            working_content.text = xml_node_text(callout).strip()
        elif callout.get('type') == 'code':
            working_content.text = '```\n' + \
                        '\n'.join([l.text for l in lines]) + \
                        '```'

    # Do the same for dashes.
    dashes = working_content.findall('.//{eregs}dash')
    for dash in dashes:
        # Dashes have to end a line, so we ignore the dash's tail
        dash_text = dash.text
        if dash_text is None:
            dash_text = ''

        dash_text = dash_text + '_____'

        # Append the dash_text to either parent or previous sibling to
        # replace the dash element.
        previous = dash.getprevious()
        if previous is not None:
            previous.tail = (previous.tail or '') + dash_text
        else:
            working_content.text = (working_content.text or '') + dash_text
        working_content.remove(dash)

    return working_content


def build_terms_layer(root):
    """
    Build the terms layer from the provided root of the XML tree.

    :param root: The root element of the XML tree.
    :type root: :class:`etree.Element`

    :return: An OrderedDict containing the locations of terms, suitable for direct
        transformation into JSON for use with the eRegs frontend.
    :rtype: :class:`collections.OrderedDict`:
    """

    definitions_dict = OrderedDict()
    terms_dict = OrderedDict()

    inf_engine = inflect.engine()
    inf_engine.defnoun('bonus', 'bonuses')

    paragraphs = root.findall('.//{eregs}paragraph') + \
        root.findall('.//{eregs}interpParagraph')

    definitions = root.findall('.//{eregs}def')

    paragraphs_with_defs = [par for par in paragraphs if par.find('{eregs}content') is not None
                            and par.find('{eregs}content').find('{eregs}def') is not None]

    for paragraph in paragraphs_with_defs:
        label = paragraph.get('label')
        marker = paragraph.get('marker') or ''
        title = paragraph.find('{eregs}title')
        content = apply_formatting(paragraph.find('{eregs}content'))
        par_text = xml_node_text(content).strip()
        definitions = content.findall('{eregs}def')

        total_offset = get_offset(paragraph, marker, title)

        for defn in definitions:
            defined_term = defn.get('term')
            if inf_engine.singular_noun(defined_term.lower()) and not \
                    defined_term.lower() in settings.SPECIAL_SINGULAR_NOUNS:
                key = inf_engine.singular_noun(defined_term.lower()) + \
                    ':' + label
            else:
                key = defined_term.lower() + ':' + label

            def_text = defn.text
            positions = find_all_occurrences(par_text, def_text)
            def_dict = OrderedDict()
            pos = positions[0]
            def_dict['position'] = [pos + total_offset, pos + len(def_text) + total_offset]
            def_dict['reference'] = label
            def_dict['term'] = defined_term
            if def_dict['position'] != []:
                definitions_dict[key] = def_dict

    for paragraph in paragraphs:
        content = apply_formatting(paragraph.find('{eregs}content'))
        terms = content.findall('.//{eregs}ref[@reftype="term"]')
        title = paragraph.find('{eregs}title')
        marker = paragraph.get('marker') or ''

        label = paragraph.get('label')
        # If this is a subparagraph of a type that wants an intro paragraph
        # and this paragraph is intro text, set the paragraph's label to reference
        # the parent's
        if wants_intro_text(paragraph.getparent()) and is_intro_text(paragraph):
            # This intro paragraph will get attached to its parent node by
            # build_reg_tree
            label = paragraph.getparent().get('label')

        if len(terms) > 0:
            terms_dict[label] = []

        total_offset = get_offset(paragraph, marker, title)

        term_positions = OrderedDict()
        term_targets = OrderedDict()

        for term in terms:
            running_par_text = content.text or ''
            for child in content.getchildren():
                if child != term:
                    tail = child.tail or ''
                    running_par_text += child.text + tail
                else:
                    break

            text = term.text
            target = term.get('target')
            defn_location = [key for key, defn in definitions_dict.items() if defn['reference'] == target]
            if len(defn_location) > 0:
                defn_location = defn_location[0]
                term_position = len(running_par_text) + total_offset
                term_positions.setdefault(text, []).append(term_position)
                term_targets[text] = defn_location

        for term, positions in term_positions.items():
            target = term_targets[term]
            ref_dict = OrderedDict()
            ref_dict['offsets'] = []
            for pos in positions:
                ref_dict['offsets'].append([pos, pos + len(term)])
            ref_dict['ref'] = target
            if len(ref_dict['offsets']) > 0 and \
                    ref_dict not in terms_dict[label]:
                terms_dict[label].append(ref_dict)

    terms_dict['referenced'] = definitions_dict

    return terms_dict


def build_toc_layer(root):
    """
    Build the paragraph table-of-contents layer from the provided root of the XML tree.

    :param root: A root element containing tableOfContents elements.
    :type root: :class:`etree.Element`

    :return: An OrderedDict containing the table of contents, suitable for direct
        transformation into JSON for use with the eRegs frontend.
    :rtype: :class:`collections.OrderedDict`:
    """

    toc_dict = OrderedDict()

    # Look for all tables of contents in the given element and add them
    # to the layer.
    tables_of_contents = root.findall('.//{eregs}tableOfContents')
    for toc in tables_of_contents:
        parent = toc.getparent()
        if parent.tag == '{eregs}content':
            parent = parent.getparent()

        label = parent.get('label')

        # Warn user about elements without labels
        if label is None:
            raise ValueError("TOC parent element {} has no label; this will cause JSON issues.".format(parent.tag))

        toc_dict[label] = []

        # Build sections
        for section in toc.findall('{eregs}tocSecEntry'):
            target = section.get('target').split('-')
            subject = section.find('{eregs}sectionSubject').text
            toc_entry = {'index': target, 'title': subject}
            toc_dict[label].append(toc_entry)

        # Build appendix sections
        for appendix_section in toc.findall('{eregs}tocAppEntry'):
            target = appendix_section.get('target').split('-')
            subject = appendix_section.find('{eregs}appendixSubject').text
            toc_entry = {'index': target, 'title': subject}
            toc_dict[label].append(toc_entry)

        # Build interp sections
        for interp_section in toc.findall('{eregs}tocInterpEntry'):
            target = interp_section.get('target').split('-')
            subject = interp_section.find('{eregs}interpTitle').text
            toc_entry = {'index': target, 'title': subject}
            toc_dict[label].append(toc_entry)

    return toc_dict


def build_keyterm_layer(root):
    """
    Build the keyterm layer from the provided XML tree.

    :param root: The root element of an XML tree containing paragraphs.
    :type root: :class:`etree.Element`

    :return: An OrderedDict containing the locations of keyterms, suitable for direct
        transformation into JSON for use with the eRegs frontend.
    :rtype: :class:`collections.OrderedDict`:
    """

    keyterm_dict = OrderedDict()
    paragraphs = root.findall('.//{eregs}paragraph') \
               + root.findall('.//{eregs}interpParagraph')

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
    """
    Build the meta layer from the provided root of the XML tree.

    :param root: The root element of the XML tree.
    :type root: :class:`etree.Element`

    :return: An OrderedDict containing the regulation metadata, suitable for direct
        transformation into JSON for use with the eRegs frontend.
    :rtype: :class:`collections.OrderedDict`:
    """

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
                      '1070': '1070', '1071': '1071',
                      '1072': '1072', '1080': '1080',
                      '1081': '1081', '1090': '1090',
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
    """
    Build the interpretations layer from the provided root of the XML tree.

    :param root: The root element of the XML tree.
    :type root: :class:`etree.Element`

    :return: An OrderedDict containing the locations of interpretations, suitable for direct
        transformation into JSON for use with the eRegs frontend.
    :rtype: :class:`collections.OrderedDict`:
    """

    layer_dict = OrderedDict()
    interpretations = root.find('.//{eregs}interpretations')

    if interpretations is not None:
        first_label = interpretations.get('label')
        first_key = first_label.split('-')[0]
        layer_dict[first_key] = [{'reference': first_label}]

        interp_sections = interpretations.findall(
            './/{eregs}interpSection')
        interp_paragraphs = interpretations.findall(
            './/{eregs}interpParagraph')
        targetted_interps = [i for i in
            interp_sections + interp_paragraphs
            if i.get('target') is not None]

        for interp in targetted_interps:
            target = interp.get('target')
            label = interp.get('label')
            layer_dict[target] = [{'reference': label}]

    return layer_dict


def build_analysis(root):
    """Build the analysis layer from the provided root of the XML tree. Only builds the references
    to the analysis layer; the actual contents of the layer are created in `build_notice`.

    :param root: The root element of the XML tree.
    :type root: :class:`etree.Element`

    :return: A dictionary specifying the locations of analyses, suitable for direct
        transformation into JSON for use with the eRegs frontend.
    :rtype: :class:`collections.OrderedDict`:
    """

    analysis_dict = OrderedDict()
    doc_number = root.find('{eregs}preamble').find('{eregs}documentNumber').text
    # Find the analysis element
    analysis_elm = root.find('.//{eregs}analysis')
    if analysis_elm is None:
        return analysis_dict

    # For each child section of the analysis, add a reference for its
    # target
    for analysis_section_elm in analysis_elm:
        # Get the target label
        label = analysis_section_elm.get('target')
        document_number = analysis_section_elm.get('notice')
        publication_date = analysis_section_elm.get('date')

        # Warn user about analysisSection elements without labels/attributes
        if label is None or document_number is None or publication_date is None:
            if label is None and document_number is None and publication_date is None:
                parent = analysis_section_elm.getparent()
                print("Error with analysisSection: Parent is {}".format(analysis_section_elm.getparent()))
                print("Element contents:\"\n{}\"".format(etree.tostring(analysis_section_elm)))
                print("Check whether a comment is in the analysis.")
            err_info = {"label": label, "notice": document_number, "date": publication_date}
            raise ValueError("In {}, analysisSection element is missing attribute information:\n{}".format(doc_number, err_info))

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
    Build the notice dictionary from the provided root of the XML tree.

    :param root: The root element of the XML tree.
    :type root: :class:`etree.Element`

    :return: An OrderedDict containing the notice, suitable for direct
        transformation into JSON for use with the eRegs frontend.
    :rtype: :class:`collections.OrderedDict`:
    """
    # Get the root label
    label = root.find('.//{eregs}part').attrib['label']

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

    # Analysis
    analysis_elm = root.find('.//{eregs}analysis')
    if analysis_elm is None:
        return notice_dict

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
                # TODO: for the moment we are reduced to inlining analysis graphics
                # TODO: as <img> elements. In our bold new future where layers
                # TODO: are abolished, this should be fixed to properly embed
                # TODO: graphics in analysis
                elif p_child_elm.tag == '{eregs}graphic':
                    url = p_child_elm.find('{eregs}url').text
                    inline_img = '<img src="{}">'.format(url)
                    paragraph_text += '\n' + inline_img + '\n'

                # If it's something else, like an em tag, include the
                # text.
                else:
                    paragraph_text += p_child_elm.text or ''

                # Append the footnote 'tail' to the paragraph text
                tail = p_child_elm.tail or ''
                paragraph_text += tail

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

    for section_elm in analysis_elm:
        # If this analysis section doesn't originate with this document
        # number, skip it.
        if section_elm.get('notice') != document_number:
            continue

        analysis_dict = build_analysis_dict(section_elm)

        # Add the parent's label to the top-level of the dict
        analysis_dict['labels'] = [section_elm.get('target')]

        # Add the analysis to the notice
        notice_dict['section_by_section'].append(analysis_dict)

    # Footnotes
    footnotes = root.findall('.//{eregs}footnote')
    for footnote_elm in footnotes:
        ref = footnote_elm.attrib['ref']
        notice_dict['footnotes'][ref] = footnote_elm.text

    return notice_dict


def is_intro_text(item):
    """
    Determines whether an element is an intro paragraph to some type of
    section because reg-site expects text in the parent node rather than
    in a subelement.

    :param item: The element to check for introductory-ness
    :type root: :class:`etree.Element`

    :return: A boolean where True indicates the element is an intro paragraph.
    :rtype: boolean
    """
    if item.find('{eregs}title') is None and \
            item.get('marker') == '' and \
            len(item) == 1:
        # Only the first child may be an intro text item
        child_num = item.getparent().index(item)
        if child_num > 1:
            return False

        # Note: item[0] is always a <content> tag - check that
        # element's children
        if len(filter(lambda child: child.tag in NON_PARA_SUBELEMENT,
                      item[0].getchildren())) == 0:
            return True

    return False

def wants_intro_text(element):
    """
    Determines whether an element is a type of element that wants
    an intro paragraph because reg-site expects text in the parent node
    rather than in a subelement.

    :param element: The element to check for wanting an intro
    :type root: :class:`etree.Element`

    :return: A boolean where True indicates the element wants an intro paragraph.
    :rtype: boolean
    """

    if element.tag in TAGS_WITH_INTRO_PARAS:
        return True
    else:
        return False

def get_offset(element, marker='', title=None):
    """
    Determines the overall offset to apply to an element from the given
    marker and title.

    :param element: The element to check for offset amounts
    :type root: :class:`etree.Element`

    :return: The amount of offset characters
    :rtype: integer
    """
    # Marker offsets
    if marker != '' and element.tag not in TAGS_WITHOUT_OFFSETS:
        marker_offset = len(marker + ' ')
    else:
        marker_offset = 0

    # Keyterm offset
    # Note: reg-site treats some elements (e.g. interpParagraphs)
    # as "special" — they don't get the keyterm text included,
    # so we don't include an offset here.
    if title is not None and title.get('type') == 'keyterm':
        keyterm_offset = len(title.text)
    else:
        keyterm_offset = 0

    return marker_offset + keyterm_offset
