#!/usr/bin/env python
from __future__ import print_function
from __future__ import unicode_literals

import importlib
import os
import sys

# Try to load the settings module
try:
    local_settings = importlib.import_module(
            os.environ.get('REGML_SETTINGS_FILE', 'settings'))
    globals().update(local_settings.__dict__)
except ImportError:
    logger.error("Unable to import settings module. "
                 "Please double-check your REGML_SETTINGS_FILE "
                 "environment variable")
    sys.exit(1)

globals().update(local_settings.__dict__)
