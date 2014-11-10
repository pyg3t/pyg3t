from __future__ import print_function
import sys
import re
import codecs
from optparse import OptionParser
from itertools import chain
from util import pyg3tmain, Encoder

from gtparse import parse


def build_parser():
    usage = '%prog [OPTION] [POFILE...]'
    description = 'write POFILEs to stdout'

    p = OptionParser(usage=usage,
                     description=description)
    p.add_option('--encode', metavar='ENCODING',
                 dest='encoding',
                 help='convert FILEs to ENCODING and update header')
    return p


@pyg3tmain
def main():
    p = build_parser()
    
    opts, args = p.parse_args()
    
    for arg in args:
        cat = parse(open(arg))
        
        if opts.encoding is not None:
            src_encoding = cat.encoding
            codecinfo = codecs.lookup(opts.encoding)

            # should result in a canonical/transferable name even if
            # people don't specify dashes or other things in the way
            # gettext likes
            dst_encoding = codecinfo.name

            header = cat.header

            lines = header.msgstr.split('\\n')
            for i, line in enumerate(lines):
                if line.startswith('Content-Type:'):
                    break
            else:
                p.error('Cannot find Content-Type in header')
            line = line.replace('charset=%s' % src_encoding,
                                'charset=%s' % dst_encoding)
            lines[i] = line
            header.msgstrs[0] = '\\n'.join(lines)
            assert len(header.msgstrs) == 1
        else:
            dst_encoding = cat.encoding
        
        out = Encoder(sys.stdout, dst_encoding)
        for msg in chain(cat, cat.obsoletes):
            print(msg.tostring(), file=out)
