# Script to strip the directional control chars from a file.
# e.g. see http://www.unicode.org/reports/tr9/tr9-29.html, part 2.1.

# Usage: python strip_control_chars.py infile outfile

# E.g.
# $ python strip_control_chars.py locale/ar/LC_MESSAGES/django.po outfile.bin
# $ mv outfile.bin locale/ar/LC_MESSAGES/django.po

# Files are assumed to have UTF-8 encoding

import sys

infile = sys.argv[1]
outfile = sys.argv[2]

print "reading %s" % infile
with open(infile, "rb") as f:
    data = f.read().decode('utf-8')

LRE = u"\u202a"
PDF = u"\u202c"

data = data.replace(LRE, "")
data = data.replace(PDF, "")

print "writing %s" % outfile
with open(outfile, "wb") as f:
    f.write(data.encode('utf-8'))
