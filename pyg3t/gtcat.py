from __future__ import print_function, unicode_literals
from optparse import OptionParser
from pyg3t.util import pyg3tmain, get_encoded_stdout, get_bytes_input
from pyg3t.gtparse import iparse
from pyg3t.charsets import get_gettext_encoding_name, \
    get_normalized_encoding_name


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
        cat = iparse(get_bytes_input(arg))
        header = next(cat)
        src_encoding = header.meta['encoding']

        if opts.encoding is not None:
            try:
                gettext_name = get_gettext_encoding_name(opts.encoding)
                dst_encoding = get_normalized_encoding_name(opts.encoding)
            except LookupError as err:
                p.error(str(err))

            lines = header.msgstr.split(r'\n')
            for i, line in enumerate(lines):
                if line.startswith('Content-Type:'):
                    break
            line = r'Content-Type: text/plain; charset=%s' % gettext_name
            lines[i] = line
            header.msgstrs[0] = r'\n'.join(lines)
        else:
            dst_encoding = src_encoding

        out = get_encoded_stdout(dst_encoding)
        print(header.tostring(), file=out)
        for msg in cat:
            print(msg.tostring(), file=out)
