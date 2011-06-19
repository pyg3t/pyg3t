import os
from subprocess import Popen, PIPE
from optparse import OptionParser, OptionGroup

from pyg3t.gtparse import parse, Message, Catalog

def build_parser():
    usage = '%prog [OPTION...] MSGSTR_FILE MSGID_FILE...'
    p = OptionParser(usage=usage,
                     description='Combine msgstrs from MSGSTR_FILE with '
                     'msgids from MSGID_FILEs where applicable, printing '
                     'the resulting catalog to stdout.  The result is '
                     'guaranteed to be template-compatible with MSGID_FILE.')
    p.add_option('--msgmerge', action='store_true',
                 help='use msgmerge for fuzzy matching.')
    mode_opts = OptionGroup(p, 'Merge modes')
    
    modes = ['left', 'right']#, 'launchpad', 'versionport']
    text = dict(left='prefer translations from MSGSTR_FILE in conflicts '
                '(default).',
                right='prefer translations from MSGID_FILE in conflicts.',
                launchpad='transfer as many strings as possible, '
                'keeping header of MSGID_FILE '
                'compatible with upload to Launchpad.',
                versionport='transfer as many strings as possible, '
                'but update header to contain ... blahblah') # XXX
    for mode in modes:
        mode_opts.add_option('--%s' % mode, action='store_const',
                             default=modes[0],
                             dest='mode', const=mode, help=text[mode])
    p.add_option_group(mode_opts)
    # option: translation project version merge mode
    # option: launchpad upload prepare mode
    
    #p.add_option('--keep-header', action='store_true',
    #             help='')
    return p

def merge_msg(src, dst):
    # oooh.  This must know the different types of comments...
    # only translator comments should be transferred
    # and fuzzy state must be correct, but that's supposed to be
    # taken care of by gtparse
    
    # XXXXXXXX comments and stuff
    #transferable_comments = [comment for comment in src.comments
    #                         if comment.startswith(
    
    srccomments = [comment for comment in src.comments
                   if comment.startswith('# ')]
    dstcomments = [comment for comment in dst.comments
                   if not comment.startswith('# ')]
    
    flags = set(dst.flags.copy())
    if 'fuzzy' in src.flags:
        flags.add('fuzzy')
    
    assert len(src.msgstrs) == len(dst.msgstrs)
    return Message(dst.msgid, src.msgstrs, dst.msgid_plural,
                   dst.msgctxt, srccomments + dstcomments,
                   flags)

def merge(cat1, cat2, overwrite=True):
    newmsgs = []
    for dstmsg in cat2:
        if dstmsg in cat1:
            srcmsg = cat1.get(dstmsg)
            state = srcmsg.state + dstmsg.state
            if ((overwrite and state in ['uu', 'ff', 'tt'])
                or state in ['fu', 'tu', 'tf']):
                msg = merge_msg(srcmsg, dstmsg)
            else:
                msg = dstmsg.copy()
        else: # yuck
            msg = dstmsg.copy()
        newmsgs.append(msg)
        msg.check()
    assert cat1.encoding == cat2.encoding
    return Catalog('-', cat1.encoding, newmsgs)

def main():
    p = build_parser()
    opts, args = p.parse_args()
    if len(args) != 2:
        p.error('Expected two arguments, got %d' % len(args))
    fname1, fname2 = args

    if opts.msgmerge:
        msgmerge = Popen(['msgmerge', fname1, fname2], 
                         stdout=PIPE,
                         stderr=PIPE)
        cat1 = parse(msgmerge.stdout)
    else:
        cat1 = parse(open(fname1))
    cat2 = parse(open(fname2))

    if opts.mode == 'left':
        overwrite = True
    else:
        assert opts.mode == 'right'
        overwrite = False
        # XXX more complicated modes?

    cat = merge(cat1, cat2, overwrite)
    for msg in cat:
        print msg#.tostring()
    #for line in cat1.obsoletes:
    #    print line, # XXX keep which obsoletes?
    # obsoletes must also be unique, and must not clash with existing msgs
