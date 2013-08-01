from optparse import OptionParser
from StringIO import StringIO

from popatch import PoPatch
from pyg3t.gtparse import parse, wrap, wrapper
from pyg3t.gtdifflib import diff, FancyWDiffFormat


def main():
    usage = '%prog [OPTION] PODIFF'
    description = 'Generate word-wise podiff from ordinary podiff'
    p = OptionParser(usage=usage, description=description)
    opts, args = p.parse_args()
    
    if len(args) != 1:
        p.error('Expected exactly one file; got %d' % len(args))
    
    fname = args[0]

    # We will, rather laboriously (for the computer, that is)
    # reconstruct 'old' and a 'new' versions from the diff using
    # PoPatch.
    #
    # After this we re-parse them and diff them word-wise.
    popatch = PoPatch()
    fd = open(fname)
    inputfd = StringIO()
    print >> inputfd, fd.read()
    
    cats = []
    #texts = []
    for isnew in [False, True]:
        inputfd.seek(0)
        #fileobj, isnew in [[oldfile, False], [newfile, True]]:
        outfd = StringIO()
        popatch.version_of_podiff(inputfd, new=isnew, output_object=outfd)
        outfd.seek(0)
        #texts.append(outfd.read())
        cat = parse(outfd)
        cats.append(cat)

    oldcat, newcat = cats

    fmt = FancyWDiffFormat()
    
    def mkdiff(old, new):
        return diff(old, new, fmt)
    def wrapdiff(declaration, old, new):
        if old is None:
            old = ''
        if new is None:
            new = ''
        return mkdiff(wrap(declaration, old), wrap(declaration, new))

    #def wrap(text):
    #    return '\n'.join(wrapper.wrap(text))

    for oldmsg, newmsg in zip(oldcat, newcat):
        #print mkdiff(''.join(oldmsg.comments), ''.join(newmsg.comments)),
        
        # wrappings might be different and introduce confusion
        # but it might be better than not wrapping at all
        if oldmsg.has_context or newmsg.has_context:
            print wrapdiff('msgctxt', oldmsg.msgctxt, newmsg.msgctxt)
        print wrapdiff('msgid', oldmsg.msgid, newmsg.msgid),
        if oldmsg.hasplurals or newmsg.hasplurals:
            print wrapdiff('msgid_plural', oldmsg.msgid_plural,
                           newmsg.msgid_plural),
        assert len(oldmsg.msgstrs) == len(newmsg.msgstrs)
        if len(oldmsg.msgstrs) == 1:
            print wrapdiff('msgstr', oldmsg.msgstr, newmsg.msgstr),
        else:
            for i, (oldmsgstr, newmsgstr) in enumerate(zip(oldmsg.msgstrs, 
                                                           newmsg.msgstrs)):
                print wrapdiff('msgstr[%d]' % i, oldmsgstr, newmsgstr),
        print
        
    #oldcat, newcat = cats
    #oldtext, newtext = texts
    #thediff = diff(oldtext, newtext, fmt)
    #print thediff
    #print 'hello'
    #print oldfile
    

    #cat = parse(fname)
    
