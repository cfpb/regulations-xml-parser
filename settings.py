__author__ = 'vinokurovy'

import os

XML_ROOT = '../regulations-schema/src'
JSON_ROOT = '../regulations-xml-json/'
XSD_FILE = os.path.join(XML_ROOT, 'eregs.xsd')

# the inflect module has a few problems... manual override for that

SPECIAL_SINGULAR_NOUNS = [
    'bonus',
    'escrow account analysis'
]