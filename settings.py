__author__ = 'vinokurovy'

import os
import inflect

XML_ROOT = '/Users/vinokurovy/Development/regulations-schema/src'
JSON_ROOT = '/Users/vinokurovy/Development/regulations-xml-json'
XSD_FILE = os.path.join(XML_ROOT, 'eregs.xsd')

# the inflect module has a few problems... manual override for that

SPECIAL_SINGULAR_NOUNS = [
    'bonus'
]