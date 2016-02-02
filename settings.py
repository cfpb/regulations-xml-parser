import os

XML_ROOT = '../regulations-xml'
JSON_ROOT = '../regulations-stub/stub'
XSD_FILE = 'http://cfpb.github.io/regulations-schema/src/eregs.xsd'

# the inflect module has a few problems... manual override for that
SPECIAL_SINGULAR_NOUNS = [
    'bonus',
    'escrow account analysis'
]

## eCFR Parser Settings

# Try to import configuration from a Python package called 'regconfig'. If
# it doesn't exist, just go with our default settings.
try:
    from regconfig import *
except ImportError:
    from regparser.default_settings import *

# OUTPUT_DIR=os.environ.get('OUTPUT_DIR', JSON_ROOT)
OUTPUT_DIR=os.environ.get('OUTPUT_DIR', XML_ROOT)
LOCAL_XML_PATHS = ['../fr-notices/',]
