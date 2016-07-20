from __future__ import print_function, unicode_literals
import codecs
from optparse import OptionParser
from itertools import chain
from pyg3t.util import pyg3tmain, get_encoded_stdout, get_bytes_input
from pyg3t.gtparse import parse
from pyg3t.charsets import get_gettext_encoding_name


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
        cat = parse(get_bytes_input(arg))

        if opts.encoding is not None:
            src_encoding = cat.encoding

            codecinfo = codecs.lookup(opts.encoding)
            dst_encoding = codecinfo.name

            header = cat.header

            lines = header.msgstr.split('\\n')
            for i, line in enumerate(lines):
                if line.startswith('Content-Type:'):
                    break
            else:
                p.error('Cannot find Content-Type in header')
            gettext_name = get_gettext_encoding_name(dst_encoding)
            line = line.replace('charset=%s' % src_encoding,
                                'charset=%s' % gettext_name)
            lines[i] = line
            header.msgstrs[0] = '\\n'.join(lines)
            assert len(header.msgstrs) == 1
        else:
            dst_encoding = cat.encoding

        out = get_encoded_stdout(dst_encoding)
        for msg in chain(cat, cat.obsoletes):
            print(msg.tostring(), file=out)
        for line in cat.trailing_comments:
            print(line, file=out)
