import os

# XSD_FILE provides the local path or URL (HTTP, FTP) to the RegML schema file.
# Schema documentation is available at http://cfpb.github.io/regulations-schema
#
# A local copy should generally be a clone or fork of
# https://github.com/cfpb/regulations-schema
# XSD_FILE = '../regulations-schema/src/eregs.xsd'
XSD_FILE = os.environ.get('XSD_FILE', '../regulations-schema/src/eregs.xsd')

# XML_ROOT is the path to Regulations XML files that this parser is
# intended to parse. Files in this location are expected to be stored
# under regulation/[PART NUMBER] and notice/[PART NUMBER] for regulation
# and notice files respectively.
#
# This should generally be a clone or fork of
# https://github.com/cfpb/regulations-xml.
# XML_ROOT = '../regulations-xml'
XML_ROOT = os.environ.get('XML_ROOT', '../regulations-xml')

# JSON_ROOT is the path to the JSON output of this parser that is
# expected by regulations-core.
#
# This should generally be a clone or fork of
# https://github.com/cfpb/regulations-stub
# JSON_ROOT = '../regulations-stub/stub'
JSON_ROOT = os.environ.get('JSON_ROOT', '../regulations-stub/stub')

# SPECIAL_SINGULAR_NOURS provides overrides for singular nouns that the
# inflect module has problems with.
SPECIAL_SINGULAR_NOUNS = [
    'bonus',
    'escrow account analysis',
    'surplus',
]

CUSTOM_NOTICE_ORDER = {

    '1005': ['2013-06861', '2012-1728', '2012-16245', '2012-19702',
             '2013-10604', '2013-19503', '2014-20681', '2016-24506',
             '2016-24503', '2017-08341', '2018-01305' ]
}

#######################################################################
## eCFR Parser Settings
# This parser provides a convenience wrapper to generate RegML files
# from eCFR XML sources of regulations using
# https://github.com/cfpb/regulations-parser.
# These are settings for the eCFR parser.

# Try to import configuration from a Python package called 'regconfig'. If
# it doesn't exist, just go with our default settings.
# For CFPB regulations, the source of this package is
# https://github.com/cfpb/regulations-configs
try:
    from regconfig import *
except ImportError:
    from regparser.default_settings import *

# Set the output directory for the eCFR parser to our XML_ROOT defined
# above. The output from the eCFR parser will be RegML files.
OUTPUT_DIR = os.environ.get('OUTPUT_DIR', XML_ROOT)

# This is a path that contains editted eCFR files (if the expected eCFR
# files don't exist, they'll be downloaded).
# For CFPB regulations, this is https://github.com/cfpb/fr-notices
LOCAL_XML_PATHS = ['../fr-notices/',]


#######################################################################
## Local Settings
# Any of the above settings can be overridden by a local_settings.py
# file. Try to import that here.
try:
    from local_settings import *
except ImportError:
    pass
