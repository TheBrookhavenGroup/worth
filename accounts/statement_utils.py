import os
from ftplib import FTP
from django.conf import settings
import gnupg


gpgemail = os.environ.get('GPG_EMAIL', 'you@example.com')
gpghomedir = os.environ.get('GPG_HOME')
gpgpass = os.environ.get('GPG_PASS')
gpg = gnupg.GPG(gnupghome=gpghomedir)


def gpg_encrypt(fn):
    # If fn = foo.txt then output file would be foo.txt.asc.
    # gpg --encrypt --sign --armor -r <email> --homedir ~/.gnupg foo.txt

    fn_out = fn + '.asc'

    with open(fn, 'rb') as f:
        status = gpg.encrypt_file(f, recipients=[gpgemail], armor=True, output=fn_out, passphrase=gpgpass)

    return status


def gpg_decrypt(fn, fn_out=None):
    # If fn = foo.txt.asc then output file would be foo.txt.
    # gpg --homedir ~/.gnupg fn.txt.asc

    with open(fn, 'rb') as f:
        status = gpg.decrypt_file(f, output=fn_out, passphrase=gpgpass)

    print(status.GPG_ERROR_CODES)
    print(status.GPG_SYSTEM_ERROR_CODES)

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
