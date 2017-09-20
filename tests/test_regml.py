import os
from tempfile import NamedTemporaryFile
from unittest import TestCase

from mock import Mock, patch

from regml import validate


class TestValidateCommand(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestValidateCommand, cls).setUpClass()
        with NamedTemporaryFile(delete=False) as f:
            f.write('<xml></xml>')
            cls.tempfile = f.name

    @classmethod
    def tearDownClass(cls):
        os.remove(cls.tempfile)
        super(TestValidateCommand, cls).tearDownClass()

    def test_invalid_filename_raises_ioerror(self):
            with self.assertRaises(IOError):
                validate(['nonexistent filename'])

    def test_valid_file_returns_successfully(self):
        with patch(
            'regml.EregsValidator',
            return_value=Mock(has_critical_errors=False)
        ):
            try:
                validate([self.tempfile])
            except SystemExit as e:
                self.assertEqual(e.code, 0)
            else:
                self.fail('invalid files should exit with code 0')

    def test_invalid_file_exits_with_code_1(self):
        with patch(
            'regml.EregsValidator',
            return_value=Mock(has_critical_errors=True)
        ):
            try:
                validate([self.tempfile])
            except SystemExit as e:
                self.assertEqual(e.code, 1)
            else:
                self.fail('invalid files should exit with code 1')
