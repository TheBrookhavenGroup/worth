#!/usr/bin/env python

import os
from glob import glob

'''
  a2ps --columns=1 2017TBG.txt -o - | ps2pdf - 2017TBG.pdf
'''

# Inputs:
y = 2022


def get_tax_dir(y):
    home = os.path.expanduser('~')
    return os.path.join(home, 'Documents/all/tax', str(y))


wd = get_tax_dir(y)
os.chdir(wd)

out_filename = os.path.join(wd, f"{y}SchwarzschildTax.pdf")
cover_filename = f"{y}Cover.pdf"
doc_order = [cover_filename, 'w2', '1099', '1256', '1098',
             'FSA', 'K1', 'DonationsDivider.pdf']

fns = glob(os.path.join(wd, '*.tex'))
tex_files = [f.strip('.tex') for f in fns]
for f in tex_files:
    os.system('pdflatex ' + f)
    os.system('pdflatex ' + f)

# order files
fns = glob(os.path.join(wd, '*.pdf'))
files = [j for i in doc_order for j in fns if i.lower() in j.lower()]
extras = set(fns) - set(files)
files.extend(extras)

cmd = 'pdftk ' + ' '.join(files) + ' cat output ' + out_filename

cmd = '"/System/Library/Automator/Combine PDF Pages.action/Contents/Resources/join.py" -o ' + out_filename + ' ' + ' '.join(files)
cmd = f"gs -q -dNOPAUSE -dBATCH -sDEVICE=pdfwrite -sOutputFile={out_filename} {' '.join(files)}"
print(cmd)
os.system(cmd)

for f in tex_files:
    os.remove(f + '.pdf')
    os.remove(f + '.aux')
    os.remove(f + '.log')

os.system('open ' + out_filename)
