from __future__ import print_function, unicode_literals
import re
from optparse import OptionParser
from difflib import SequenceMatcher

from pyg3t.gtparse import parse
from pyg3t.util import Colorizer, pyg3tmain, get_encoded_output
from pyg3t.popatch import split_diff_as_bytes


def print_msg_diff(differ, oldmsg, newmsg, fd):
    oldcomments = ''.join(oldmsg.comments).rstrip('\n')
    newcomments = ''.join(newmsg.comments).rstrip('\n')
    print(differ.diff(oldcomments, newcomments), file=fd)
    if oldmsg.flags or newmsg.flags:
        print(differ.diff(oldmsg.flagstostring()[:-1], # ignore last newline
                          newmsg.flagstostring()[:-1]), file=fd)
    if oldmsg.has_context or newmsg.has_context:
        print(differ.maybe_wrapdiff('msgctxt', oldmsg.msgctxt,
                                    newmsg.msgctxt),
              file=fd)
    print(differ.maybe_wrapdiff('msgid', oldmsg.msgid, newmsg.msgid),
          file=fd)
    if oldmsg.isplural or newmsg.isplural:
        print(differ.maybe_wrapdiff('msgid_plural', oldmsg.msgid_plural,
                                    newmsg.msgid_plural), file=fd)
    if len(oldmsg.msgstrs) == 1:
        print(differ.maybe_wrapdiff('msgstr', oldmsg.msgstr, newmsg.msgstr),
              file=fd)
    else:
        for i, (oldmsgstr, newmsgstr) in enumerate(zip(oldmsg.msgstrs,
                                                       newmsg.msgstrs)):
            print(differ.maybe_wrapdiff('msgstr[%d]' % i, oldmsgstr,
                                        newmsgstr), file=fd)


class MSGDiffer:
    def __init__(self):
        self.tokenizer = re.compile(r'(\s+|[^\s\w])')
        self.equalcolor = Colorizer(None)
        self.oldcolor = Colorizer('old')
        self.newcolor = Colorizer('new')
        self.maxlinelength = 100

    def difftokens(self, old, new):
        oldwords = self.tokenizer.split(old)
        newwords = self.tokenizer.split(new)

        def isgarbage(string):
            return string.isspace() #False
        differ = SequenceMatcher(isgarbage, a=oldwords, b=newwords)

        words = []
        colors = []

        def append(tokens, color):
            for token in tokens:
                words.append(token)
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
        return words, colors

    def colorize(self, words, colors):
        # XXX the actual way we do things, it sometimes adds
        # a trailing newline.  This we will justs strip away here.
        # Which is a bit illogical and confusing, admittedly
        return ''.join(color.colorize(w)
                       for color, w in zip(colors, words)).rstrip('\n')

    def diff(self, old, new):
        words, colors = self.difftokens(old, new)
        return self.colorize(words, colors)

    def maybe_wrapdiff(self, header, old, new):
        words, colors = self.difftokens(old, new)
        length = len(header) + 3 + sum(len(w) for w in words)
        if length < self.maxlinelength and not any(r'\n' in w for w in words):
            words = [header, ' "'] + words + ['"\n']
            colors = [self.equalcolor, self.equalcolor] + colors + \
                [self.equalcolor]
            return self.colorize(words, colors)
        else:
            return self.wrapdiff(header, old, new)

    def wrapdiff(self, header, old, new):
        words, colors = self.difftokens(old, new)

        newwords = []
        newcolors = []

        def newappend(w, color):
            newwords.append(w)
            newcolors.append(color)

        newappend('%s ""\n' % header, self.equalcolor)
        nchars = 0

        for w, c in zip(words, colors):
            lenw = len(w)
            if nchars == 0:
                newappend('"', self.equalcolor)
                nchars = 1
            elif nchars + lenw > self.maxlinelength:
                newappend('"\n"', self.equalcolor)
                nchars = 1
            newappend(w, c)
            nchars += len(w)
            if w.endswith('\\n'):# and c != red:
                newappend('"\n', self.equalcolor)
                nchars = 0

        if nchars > 0:
            newappend('"', self.equalcolor)
        # XXX len(words) == 0 should not happen when we have to wrap
        #if len(words) == 0 or not w.endswith('\\n'):
        #    newappend(quote, yellow)

        return self.colorize(newwords, newcolors)


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
    fd = open(fname, 'rb')

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
        print(file=out)
