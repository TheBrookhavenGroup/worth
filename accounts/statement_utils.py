import os
from ftplib import FTP
from django.conf import settings
import gnupg


gpg = gnupg.GPG(gnupghome=settings.GPG_HOME)


def gpg_encrypt(fn):
    # If fn = foo.txt then output file would be foo.txt.asc.
    # gpg --encrypt --sign --armor -r <email> --homedir ~/.gnupg foo.txt

    fn_out = fn + '.asc'
    gpgemail = settings.GPG_EMAIL
    gpgpass = settings.GPG_PASS

    with open(fn, 'rb') as f:
        status = gpg.encrypt_file(f,
                                  recipients=[gpgemail],
                                  armor=True,
                                  output=fn_out,
                                  passphrase=gpgpass)

    return status


def gpg_decrypt(fn, fn_out=None):
    # If fn = foo.txt.asc then output file would be foo.txt.
    # gpg --homedir ~/.gnupg fn.txt.asc

    if fn_out is None:
        fn_out = fn.strip('.pgp')

    gpgpass = settings.GPG_PASS
    with open(fn, 'rb') as f:
        status = gpg.decrypt_file(f, output=fn_out, passphrase=gpgpass)

    return fn_out, status


def ib_statements(decrypt=False):
    user = settings.IB_FTP_USER
    pw = settings.IB_FTP_PW
    server = settings.IB_FTP_SERVER

    ftp = FTP(server)
    ftp.login(user, pw)
    ftp.cwd('outgoing')
    ftp_files = []
    ftp.retrlines('NLST', ftp_files.append)
    file_names = []
    for f in ftp_files:
        fn = os.path.join('/Users/ms/Downloads', f)
        file_names.append(fn)
        print(f'Saving {fn}')
        with open(fn, 'wb') as fh:
            ftp.retrbinary('RETR ' + f, fh.write)
    if decrypt:
        file_names = [gpg_decrypt(fn)[0] for fn in file_names]

    return file_names
