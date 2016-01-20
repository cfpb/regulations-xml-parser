import os

XML_ROOT = '../regulations-stub/xml'
JSON_ROOT = '../regulations-stub/stub'
XSD_FILE = '../regulations-schema/src/eregs.xsd'

# the inflect module has a few problems... manual override for that

SPECIAL_SINGULAR_NOUNS = [
    'bonus',
    'escrow account analysis'
]

## eCFR Parser Settings
from regparser.default_settings import *

# OUTPUT_DIR=os.environ.get('OUTPUT_DIR', "../regulations-stub/stub/")
OUTPUT_DIR=os.environ.get('OUTPUT_DIR', "../regulations-stub/xml/")
# OUTPUT_DIR="../regulations-stub/stub/"
LOCAL_XML_PATHS = ['../fr-notices/',]
