__author__ = 'vinokurovy'

from regulation.node import RegNode, xml_node_text

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
        node.text = content_text
        # node.text = '({}) {}'.format(root.get('marker'), content_text)
        node.node_type = parent.node_type

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