from __future__ import print_function, unicode_literals
from optparse import OptionParser

from pyg3t.util import (pyg3tmain, get_encoded_output, get_bytes_input, ansi,
                        regex)
from pyg3t.gtparse import iparse
from pyg3t.charsets import (get_gettext_encoding_name, set_header_charset,
                            get_normalized_encoding_name)


colors = {}
for key in ['msgid', 'msgstr', 'msgctxt', 'msgid_plural', 'msgstr[%d]']:
    colors[key] = ansi.light_red(key)
for key in ['#|', '#~']:
    colors[key] = ansi.purple(key)
for key in ['#,']:
    colors[key] = ansi.light_cyan(key)


wordsep = regex(r'(\s+|\\n)')


def color(colorname, string):
    if string is None:
        return None
    if string == '':
        return string
    return ansi[colorname](string)


def add_colors(msg):
    msg.comments = [color('light blue', comment)
                    for comment in msg.comments]
    if msg.msgid is None:
        return
    msg.previous_msgctxt = color('purple', msg.previous_msgctxt)
    msg.previous_msgid = color('green', msg.previous_msgid)
    msg.msgctxt = color('light purple', msg.msgctxt)
    msg.msgid = color('light green', msg.msgid)
    msg.msgid_plural = color('light green', msg.msgid_plural)
    if msg.flags:
        msg.flags = set(color('light cyan', flag)
                        for flag in msg.flags)
    for i, msgstr in enumerate(msg.msgstrs):
        msg.msgstrs[i] = color('yellow', msgstr)


def build_parser():
    usage = '%prog [OPTION] [POFILE...]'
    description = 'write POFILEs to stdout'

    p = OptionParser(usage=usage,
                     description=description)
    p.add_option('--encode', metavar='ENCODING',
                 dest='encoding',
                 help='convert FILEs to ENCODING and update header')
    p.add_option('-c', '--color', action='store_true',
                 help='highlight syntax in messages')
    return p


@pyg3tmain(build_parser)
def main(parser):
    opts, args = parser.parse_args()

    for arg in args:
        fd = get_bytes_input(arg)
        cat = iparse(fd)
        header = next(cat)
        src_encoding = header.meta['encoding']

        if opts.encoding is not None:
            try:
                gettext_name = get_gettext_encoding_name(opts.encoding)
                dst_encoding = get_normalized_encoding_name(opts.encoding)
            except LookupError as err:
                parser.error(str(err))

            set_header_charset(header, gettext_name)
        else:
            dst_encoding = src_encoding

        def messages():
            yield header
            for msg in cat:
                yield msg

        out = get_encoded_output(dst_encoding)

        for msg in messages():
            if opts.color:
                add_colors(msg)
                string = msg.tostring(colorize=colors.get)
            else:
                string = msg.tostring()
            print(string, file=out)
