from __future__ import print_function, unicode_literals
from optparse import OptionParser
from difflib import SequenceMatcher
try:
    from itertools import zip_longest  # Py3
except ImportError:
    from itertools import izip_longest as zip_longest  # Py2

from pyg3t.gtparse import parse
from pyg3t.message import Message
from pyg3t.util import (ansi, pyg3tmain, get_encoded_output, get_bytes_input,
                        regex)
from pyg3t.popatch import split_diff_as_bytes


def print_msg_diff(differ, msg1, msg2, fd):
    kwargs = {}
    comments1 = ''.join(msg1.comments)
    comments2 = ''.join(msg2.comments)
    kwargs['comments'] = differ.diff(comments1, comments2)
    commonflags = msg1.flags.intersection(msg2.flags)
    flags1only = msg1.flags.difference(msg2.flags)
    flags2only = msg2.flags.difference(msg1.flags)
    kwargs['flags'] = set().union(commonflags,
                                  map(ansi.old, flags1only),
                                  map(ansi.new, flags2only))

    kwargs['msgid'] = differ.diff(msg1.msgid, msg2.msgid)
    if msg1.has_previous_msgctxt or msg2.has_previous_msgctxt:
        kwargs['previous_msgctxt'] = differ.diff(msg1.previous_msgctxt,
                                                 msg2.previous_msgctxt)
    if msg1.has_previous_msgid or msg2.has_previous_msgid:
        kwargs['previous_msgid'] = differ.diff(msg1.previous_msgid,
                                               msg2.previous_msgid)
    if msg1.has_context or msg2.has_context:
        kwargs['msgctxt'] = differ.diff(msg1.msgctxt,
                                        msg2.msgctxt)
    if msg1.isplural or msg2.isplural:
        kwargs['msgid_plural'] = differ.diff(msg1.msgid_plural,
                                             msg2.msgid_plural)

    diffmsgstrs = []
    for msgstr1, msgstr2 in zip_longest(msg1.msgstrs, msg2.msgstrs,
                                        fillvalue=''):
        diffmsgstr = differ.diff(msgstr1, msgstr2)
        diffmsgstrs.append(diffmsgstr)
    kwargs['msgstr'] = diffmsgstrs
    msg = Message(**kwargs)
    print(msg.tostring(), file=fd)


class MSGDiffer:
    def __init__(self):
        # Tokenizer splits strings over escaped newlines, whitespace,
        # and punctuation.  The tokens, after splitting, will include
        # the separators.
        self.tokenizer = regex(r'(\\n|\s+|[^\s\w])')
        self.equalcolor = lambda string: string
        self.oldcolor = ansi.old
        self.newcolor = ansi.new
        self.maxlinelength = 100

    def difftokens(self, old, new):
        oldwords = self.tokenizer.split(old)
        newwords = self.tokenizer.split(new)

        def isgarbage(string):
            return string.isspace() and '\n' not in string
        differ = SequenceMatcher(isgarbage, a=oldwords, b=newwords)

        chunks = []
        colors = []

        def append(tokens, color):
            chunks.append(tokens)
            colors.append(color)

        for op, s1beg, s1end, s2beg, s2end in differ.get_opcodes():
            w1 = oldwords[s1beg:s1end]
            w2 = newwords[s2beg:s2end]

            if op == 'equal':
                append(w1, self.equalcolor)
            elif op == 'insert':
                append(w2, self.newcolor)
            elif op == 'replace':
                append(w1, self.oldcolor)
                append(w2, self.newcolor)
            elif op == 'delete':
                append(w1, self.oldcolor)
        return chunks, colors

    def colorize(self, chunks, colors):
        # XXX the actual way we do things, it sometimes adds
        # a trailing newline.  This we will justs strip away here.
        # Which is a bit illogical and confusing, admittedly
        return ''.join(color(''.join(chunk))
                       for color, chunk in zip(colors, chunks))

    def diff(self, old, new):
        if old is None:
            old = ''
        if new is None:
            new = ''
        words, colors = self.difftokens(old, new)
        return self.colorize(words, colors)


def build_parser():
    usage = '%prog [OPTION] PODIFF'
    description = 'Generate word-wise podiff from ordinary podiff'
    p = OptionParser(usage=usage, description=description)
    p.add_option('--previous', action='store_true',
                 help='display changes inferred from previous msgid'
                 ' in comment (i.e. #| msgid)'
                 ' as if they were actual changes to msgid')
    return p


@pyg3tmain(build_parser)
def main(p):
    opts, args = p.parse_args()

    if len(args) != 1:
        p.error('Expected exactly one file; got %d' % len(args))

    fname = args[0]

    # We will, rather laboriously (for the computer, that is)
    # reconstruct 'old' and a 'new' versions from the diff using
    # PoPatch.
    #
    # After this we re-parse them and diff them word-wise.
    fd = get_bytes_input(fname)

    oldbytes, newbytes = split_diff_as_bytes(fd)
    oldcat = parse(iter(oldbytes))
    newcat = parse(iter(newbytes))

    out = get_encoded_output('utf8')
    differ = MSGDiffer()

    if len(oldcat) != len(newcat): # XXX not very general
        p.error('The catalogs have different length.  Not supported '
                'by gtwdiff as of now')

    for oldmsg, newmsg in zip(oldcat, newcat):
        if opts.previous:
            if oldmsg.has_previous_msgid:
                if oldmsg.msgid != newmsg.msgid:
                    p.error('Old and new msgids differ!  This is not '
                            'supported with the --previous option')
                oldmsg.msgid = oldmsg.previous_msgid

        # Unfortunately the metadata is not restored when patching
        # The method format_linenumber should produce whatever podiff
        # normally produces.
        #print format_linenumber(newmsg.meta['lineno'], newcat.fname)
        print_msg_diff(differ, oldmsg, newmsg, out)
