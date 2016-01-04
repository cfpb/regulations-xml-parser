from node import *
from tree import *
from itertools import product

def compare_trees(root1, root2):

    hash1 = hash(root1)
    hash2 = hash(root2)

    if hash1 == hash2:
        print 'OK: Roots {} and {} are equal'.format(root1.string_label, root2.string_label)

    else:
        print 'DIFF: Roots {} and {} differ'.format(root1.string_label, root2.string_label)

    if len(root1.children) != len(root2.children):
        print 'DIFF: Root {} has {} children and root {} has {} children'.format(
            root1.string_label, len(root1.children), root2.string_label, len(root2.children)
        )

    #if len(root1.children) == len(root2.children):
    for child1, child2 in zip(root1.children, root2.children):
        compare_trees(child1, child2)


def compare_trees_by_label(root1, root2):

    root1_labels = root1.labels()
    root2_labels = root2.labels()

    common_labels = set(root1_labels) & set(root2_labels)

    # print 'The two trees have the following labels in common:\n {}'.format(common_labels)

    only_root1_labels = [label for label in root1_labels if label not in root2_labels]
    only_root2_labels = [label for label in root2_labels if label not in root1_labels]

    # print 'Only the first tree has the following labels:\n {}'.format(only_root1_labels)
    # print 'Only the second tree has the following labels:\n {}'.format(only_root2_labels)

    for l1 in common_labels:

        def find_by_label(node):
            if node.string_label == l1:
                return True
            else:
                return False

        n1 = root1.find_node(find_by_label)[0]
        n2 = root2.find_node(find_by_label)[0]

        if hash(n1) == hash(n2):
            pass
        else:
            pass


def recursive_comparison(root1, root2):

    r1_label = root1.string_label
    r2_label = root2.string_label

    if hash(root1) != hash(root2):
        # if the hashes of the node properties are equal then the difference
        # is in the children
        if root1.interior_hash == root2.interior_hash:
            if root1.string_label != root2.string_label:
                print 'r1:{} has been renamed to r2:{}'.format(r1_label, r2_label)
        else:
            pass

    else:
        print 'r1:{} and r2:{} are the same node and all their subnodes are equal'.format(r1_label, r2_label)

