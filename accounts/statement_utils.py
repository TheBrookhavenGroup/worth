import os
from ftplib import FTP
from django.conf import settings


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
