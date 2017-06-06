from node import *
from tree import *
from itertools import product


def load_xml(filename):
    with open(filename, 'r') as f:
        data = f.read()
        return etree.fromstring(data)


def extract_version(xml_tree):

    preamble = xml_tree.find('.//{eregs}preamble')
    doc_number = preamble.find('{eregs}documentNumber').text
    eff_date = preamble.find('{eregs}effectiveDate').text
    version = ':'.join([doc_number, eff_date])
    return version


def gather_regnode_labels(root):

    labels = []

    def recursive_gather(node):
        if node.label is not None:
            labels.append(node.label)
        for child in node.children:
            recursive_gather(child)

    recursive_gather(root)

    return labels


def diff_trees(left_version, right_version):

    left_tree = RegNode.objects.get(tag='regulation', version=left_version)
    right_tree = RegNode.objects.get(tag='regulation', version=right_version)

    left_tree.get_descendants()
    right_tree.get_descendants()

    left_tree.compute_merkle_hash()
    right_tree.compute_merkle_hash()

    left_labels = set(gather_regnode_labels(left_tree))
    right_labels = set(gather_regnode_labels(right_tree))

    only_left_labels = left_labels - right_labels
    only_right_labels = right_labels - left_labels

    both_labels = left_labels & right_labels

    # only right labels were added
    for label in only_right_labels:
        pass


def gather_labels(tree):

    labels = []

    def recursive_gather(node):
        if node.get('label') is not None:
            labels.append(node.get('label'))
        for child in node:
            recursive_gather(child)

    recursive_gather(tree)

    return labels


def set_descendants_property(root, prop_name, prop_value):

    root.set(prop_name, prop_value)

    for child in root:
        set_descendants_property(child, prop_name, prop_value)


def set_modified_toc_entry(root, element):

    if element.get('label', None) is not None:
        label = element.get('label')
        section_label = '-'.join(label.split('-')[0:2])
        sec_toc_item = root.find('.//{{eregs}}tocSecEntry[@target="{}"]'.format(section_label))
        app_toc_item = root.find('.//{{eregs}}tocAppEntry[@target="{}"]'.format(section_label))
        int_toc_item = root.find('.//{{eregs}}tocInterpEntry[@target="{}"]'.format(section_label))

        #print 'looking for toc element for {}'.format(section_label)
        #import ipdb; ipdb.set_trace()
        for item in [sec_toc_item, app_toc_item, int_toc_item]:
            if item is not None:
                item.set('action', 'modified')


def merge_tocs(left_toc, right_toc):

    left_toc_entries = left_toc.children
    right_toc_entries = right_toc.children

    merged_toc = etree.Element('{eregs}tableOfContents')

    current_left = left_toc_entries[0]
    current_right = right_toc_entries[0]
    stop = False

    while not stop:
        if current_left.tag == current_right.tag:
            pass

    # deleted labels
    only_left_entries = [entry for entry in left_toc_entries if entry.get('target') is not None
                         and right_toc.find('.//*[target="{}"]'.format(entry.get('target'))) is None]
    # added labels
    only_right_entries = [entry for entry in right_toc_entries if entry.get('target') is not None
                          and left_toc.find('.//*[target="{}"]'.format(entry.get('target'))) is None]

    common_entries = [entry for entry in left_toc_entries if entry.get('target') is not None
                      and right_toc.find('.//*[target="{}"]'.format(entry.get('target'))) is not None]


def diff_files(left_filename, right_filename, output_file='diff.xml'):

    left_tree = load_xml(left_filename)
    right_tree = load_xml(right_filename)

    comments = left_tree.xpath('//comment()')
    for comment in comments:
        parent = comment.getparent()
        parent.remove(comment)

    comments = right_tree.xpath('//comment()')
    for comment in comments:
        parent = comment.getparent()
        parent.remove(comment)

    left_labels = gather_labels(left_tree)
    right_labels = gather_labels(right_tree)

    right_toc = right_tree.find('.//{eregs}tableOfContents')
    left_toc = left_tree.find('.//{eregs}tableOfContents')

    only_left_labels = [label for label in left_labels if label not in right_labels]
    only_right_labels = [label for label in right_labels if label not in left_labels]

    common_labels = [label for label in left_labels if label in right_labels]

    # clear out any right-hand labels that aren't top-level
    top_level_right_labels = set()
    for label in only_right_labels:
        element = right_tree.find('.//*[@label="{}"]'.format(label))
        current_parent = element.getparent()
        last_label = element.get('label')
        while current_parent.get('label') in only_right_labels:
            last_label = current_parent.get('label')
            current_parent = current_parent.getparent()
        top_level_right_labels.add(last_label)


    #print 'only right labels:', only_right_labels
    #print 'top level right labels:', top_level_right_labels
    #print 'only left labels:', only_left_labels

    for label in top_level_right_labels:
        # print 'Processing right label {}'.format(label)
        element = right_tree.find('.//*[@label="{}"]'.format(label))
        # print 'element {} was added:'.format(label)
        # print etree.tostring(element, pretty_print=True)
        common_ancestor, prev_sibling = left_tree_ancestor(left_tree, element)
        #print 'the ancestor in the left tree is', common_ancestor.get('label'), 'to be inserted after', prev_sibling.get('label')
        #element.attrib['action'] = 'added'
        set_descendants_property(element, 'action', 'added')
        if prev_sibling is not None:
            prev_sibling.addnext(deepcopy(element))
            #print 'adding {} after {}'.format(element.get('label'), prev_sibling.get('label'))
        else:
            common_ancestor.append(deepcopy(element))

    for label in only_left_labels:
        # print 'Processing left label {}'.format(label)
        element = left_tree.find('.//*[@label="{}"]'.format(label))
        #print 'element {} was deleted:'.format(label)
        #element.attrib['action'] = 'deleted'
        set_descendants_property(element, 'action', 'deleted')
        # print etree.tostring(element, pretty_print=True)

    for label in common_labels:
        # print 'Processing common label {}'.format(label)
        # print 'analyzing common label', label
        left_element = left_tree.find('.//*[@label="{}"]'.format(label))
        right_element = right_tree.find('.//*[@label="{}"]'.format(label))
        assert (left_element.tag == right_element.tag)

        if left_element.tag == '{eregs}section':
            left_subject_el = left_element.find('{eregs}subject')
            right_subject_el = right_element.find('{eregs}subject')
            left_subject = left_subject_el.text.strip()
            right_subject = right_subject_el.text.strip()

            if left_subject != right_subject:
                #print 'section {} subject has changed from\n {}\n to\n {}'.format(label, left_subject, right_subject)
                left_subject_el.tag = '{eregs}leftSubject'
                right_subject_el.tag = '{eregs}rightSubject'
                left_subject_el.addnext(right_subject_el)
                left_element.attrib['action'] = 'modified'
                set_modified_toc_entry(right_tree, left_element)

        elif left_element.tag == '{eregs}interpSection':
            try:
                left_title_el = left_element.find('{eregs}title')
                left_title = left_title_el.text.strip()
            except AttributeError:
                left_title = ''
            try:
                right_title_el = right_element.find('{eregs}title')
                right_title = right_title_el.text.strip()
            except AttributeError:
                right_title = ''

            if left_title != right_title:
                #print 'section {} title has changed from\n {}\n to\n {}'.format(label, left_title, right_title)
                if left_title_el is not None and right_title_el is not None:
                    left_title_el.tag = '{eregs}leftTitle'
                    right_title_el.tag = '{eregs}rightTitle'
                    left_title_el.addnext(deepcopy(right_title_el))
                    left_element.attrib['action'] = 'modified'
                    set_modified_toc_entry(right_tree, left_element)

        elif left_element.tag == '{eregs}paragraph' or left_element.tag == '{eregs}interpParagraph':
            try:
                left_title_el = left_element.find('{eregs}title')
                left_title = left_title_el.text.strip()
            except AttributeError:
                left_title = ''
            try:
                right_title_el = left_element.find('{eregs}title')
                right_title = right_title_el.text.strip()
            except AttributeError:
                right_title = ''

            if left_title != right_title:
                #print 'paragraph {} title has changed from\n {}\n to\n {}'.format(label, left_title, right_title)
                if left_title_el is not None and right_title_el is not None:
                    left_title_el.tag = '{eregs}leftTitle'
                    right_title_el.tag = '{eregs}rightTitle'
                    left_title_el.addnext(deepcopy(right_title_el))
                    left_element.attrib['action'] = 'modified'
                    set_modified_toc_entry(right_tree, left_element)

            left_content = left_element.find('{eregs}content')
            left_text = xml_node_text(left_content).strip()
            right_content = right_element.find('{eregs}content')
            right_text = xml_node_text(right_content).strip()
            if left_text != right_text:
                # print 'paragraph {} text has changed from\n {}\n to \n {}'.format(label, left_text, right_text)
                left_content.tag = '{eregs}leftContent'
                right_content.tag = '{eregs}rightContent'
                left_content.addnext(deepcopy(right_content))
                left_element.attrib['action'] = 'modified'
                set_modified_toc_entry(right_tree, left_element)

    #with open(output_file, 'w') as f:
    #    f.write(etree.tostring(left_tree, pretty_print=True))
    left_toc.getparent().replace(left_toc, right_toc)
    return left_tree, extract_version(left_tree), extract_version(right_tree)


def left_tree_ancestor(left_tree, right_node):
    """
    :param left_tree: The left XML tree
    :param right_node: A node from the right tree that was added
    :return: The element from the left tree under which the right_node can be inserted
    and the element *after* which it is to be inserted
    """

    common_ancestor = None
    left_sibling = None
    stop = False
    current_right = right_node

    while common_ancestor is None and not stop:
        right_node_parent = current_right.getparent()
        left_ancestor = left_tree.find('.//*[@label="{}"]'.format(right_node_parent.get('label')))
        #if left_ancestor is None:
        #    import ipdb; ipdb.set_trace()

        if left_ancestor is not None:
            stop = True
            common_ancestor = left_ancestor
        else:
            current_right = right_node_parent

    stop = False

    while left_sibling is None and not stop:
        for child in common_ancestor:
            right_previous = right_node.getprevious()
            if right_previous is not None:
                if child.get('label') == right_node.getprevious().get('label'):
                    left_sibling = child
        stop = True

    return common_ancestor, left_sibling


def merge_text_diff(diff):

    text = ''
    flag = 'common' # other values: add, delete
    for d in diff:
        if d[0] == ' ':
            if flag == 'delete':
                text += '</del>' + d[2]
            elif flag == 'add':
                text += '</ins>' + d[2]
            elif flag == 'common':
                text += d[2]
            flag = 'common'
        elif d[0] == '-':
            if flag == 'common':
                text += '<del>' + d[2]
            elif flag == 'delete':
                text += d[2]
            elif flag == 'add':
                text += '</ins>' + '<del>' + d[2]
            flag = 'delete'
        elif d[0] == '+':
            if flag == 'common':
                text += '<ins>' + d[2]
            elif flag == 'add':
                text += d[2]
            elif flag == 'delete':
                text += '</del>' + '<ins>' + d[2]
            flag = 'add'

    if flag == 'add':
        text += '</ins>'
    elif flag == 'delete':
        text += '</del>'

    return text
