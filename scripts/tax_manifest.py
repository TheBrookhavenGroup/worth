#!/Users/ms/dev/tbg/worth/.venv/bin/python


import os
import sys
from glob import glob
import configparser
from pypdf import PdfWriter

"""
  a2ps --columns=1 2017TBG.txt -o - | ps2pdf - 2017TBG.pdf
"""


def main():
    if len(sys.argv) < 2:
        print("Usage: taxmanifest <year>")
        sys.exit(1)

    y = int(sys.argv[1])
    print(f"Running tax manifest for {y}")

    config = configparser.ConfigParser()
    config.read("/Users/ms/.worth")
    config = config["TAX"]

    def get_tax_dir(y):
        home = os.path.expanduser("~")
        return os.path.join(home, config["path"], str(y))

    wd = get_tax_dir(y)
    os.chdir(wd)

    name = config["name"]
    out_filename = os.path.join(wd, f"{y}{name}Tax.pdf")
    doc_order = config["order"].split(" ")

    fns = glob(os.path.join(wd, "*.tex"))
    tex_files = [f.strip(".tex") for f in fns]
    for f in tex_files:
        os.system("pdflatex " + f)
        os.system("pdflatex " + f)

    # order files
    # glob all *.pdf and *.PDF files
    fns = glob(os.path.join(wd, "*.pdf")) + glob(os.path.join(wd, "*.PDF"))
    fns = set(fns)

    files = [f for i in doc_order for f in fns if i.lower() in f.lower()]

    # Get unique list of files but preserve order
    files = sorted(set(files), key=lambda x: files.index(x))

    extras = fns - set(files)
    print(f"Files not included: {extras}")

    print(f"Files included: {files}")

    # Merge files
    writer = PdfWriter()
    for f in files:
        writer.append(f)
    writer.write(out_filename)
    writer.close()

    for f in tex_files:
        os.remove(f + ".pdf")
        os.remove(f + ".aux")
        os.remove(f + ".log")

    os.system("open " + out_filename)


if __name__ == "__main__":

    main()
