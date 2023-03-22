import os
from django.test import TestCase, tag
from .statement_utils import gpg_encrypt, gpg_decrypt


@tag('inhibit_test')
class GPGTests(TestCase):
    def setUp(self):
        self.fn = os.path.join(os.path.dirname(__file__), 'test_files/foo.txt')

    def tearDown(self):
        os.remove(self.fn + '.asc')
        os.remove(self.fn + '.decrypted')

    def test_encrypt(self):
        status = gpg_encrypt(fn=self.fn)
        self.assertTrue(status.ok)

        fn_out = self.fn + '.decrypted'
        status = gpg_decrypt(self.fn + '.asc', fn_out=fn_out)
        self.assertTrue(status.ok)
