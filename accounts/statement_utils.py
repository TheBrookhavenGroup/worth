import os
from ftplib import FTP
from django.conf import settings
import gnupg


def gpg_encrypt(fn):
    # If fn = foo.txt then output file would be foo.txt.asc.
    # gpg --encrypt --sign --armor -r <email> --homedir ~/.gnupg foo.txt

    email = os.environ.get('GPG_EMAIL')
    gpghomedir = os.environ.get('GPG_HOME')
    gpg = gnupg.GPG(gnupghome=gpghomedir)

    fn_out = fn + '.asc'

    with open(fn, 'rb') as f:
        status = gpg.encrypt_file(f, recipients=[email], armor=True, output=fn_out, passphrase='foo')

    return status


def gpg_decrypt(fn, fn_out=None):
    # If fn = foo.txt.asc then output file would be foo.txt.
    # gpg --homedir ~/.gnupg fn.txt.asc
    gpghomedir = os.environ.get('GPG_HOME')
    gpg = gnupg.GPG(gnupghome=gpghomedir)

    with open(fn, 'rb') as f:
        status = gpg.decrypt_file(f, output=fn_out)

    return status


def ib_statements():
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
    return file_names
