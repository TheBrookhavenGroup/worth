import os
import shutil
import tempfile
from unittest import mock

import gnupg
from django.test import TestCase, override_settings, tag

from .statement_utils import gpg_encrypt, gpg_decrypt


TEST_GPG_EMAIL = "tester@example.com"
TEST_GPG_PASS = "test-passphrase"


@tag("inhibit_test")
class GPGTests(TestCase):
    def setUp(self):
        self.fn = os.path.join(os.path.dirname(__file__), "test_files/foo.txt")
        self.gpg_home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.gpg_home, True)

        self.settings_override = override_settings(
            GPG_HOME=self.gpg_home,
            GPG_EMAIL=TEST_GPG_EMAIL,
            GPG_PASS=TEST_GPG_PASS,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.gpg = gnupg.GPG(gnupghome=self.gpg_home)
        key_input = self.gpg.gen_key_input(
            name_email=TEST_GPG_EMAIL,
            name_real="Worth Test",
            passphrase=TEST_GPG_PASS,
            key_type="RSA",
            key_length=1024,
        )
        self.gpg.gen_key(key_input)

        self.gpg_patcher = mock.patch("accounts.statement_utils.gpg", self.gpg)
        self.gpg_patcher.start()
        self.addCleanup(self.gpg_patcher.stop)

    def tearDown(self):
        for suffix in (".asc", ".decrypted"):
            fn = self.fn + suffix
            if os.path.exists(fn):
                os.remove(fn)

    def test_encrypt(self):
        status = gpg_encrypt(fn=self.fn)
        self.assertTrue(status.ok)

        fn_out = self.fn + ".decrypted"
        fn, status = gpg_decrypt(self.fn + ".asc", fn_out=fn_out)
        self.assertTrue(status.ok)
