import os
from ftplib import FTP


def ib_statements():
    pw = os.environ['IB_FTP_PW']

    user = 'msch73wib8'
    server = 'ftp.interactivebrokers.com'

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
