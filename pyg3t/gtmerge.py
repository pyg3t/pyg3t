import os
from subprocess import Popen, PIPE
from optparse import OptionParser, OptionGroup

from pyg3t.gtparse import parse, Message, Catalog
from pyg3t.util import pyg3tmain


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
    
    modes = ['left', 'right', 'translationproject']
    #, 'launchpad', 'versionport']
    text = dict(left='prefer translations from MSGSTR_FILE in conflicts '
                '(default).',
                right='prefer translations from MSGID_FILE in conflicts.',
                translationproject='merge MSGSTR_FILE into all MSGID_FILES '
                'and write to separate files.  Useful for merging to many '
                'older versions on translationproject.org',
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

def merge_msg(strmsg, idmsg):
    strcomments = [comment for comment in strmsg.comments
                   if comment.startswith('# ') or comment == '#\n']
    idcomments = [comment for comment in idmsg.comments
                  if not comment.startswith('# ')
                  and not comment == '#\n'
                  and not comment.startswith('#|')]
    # This will remove #|-comments
    
    flags = idmsg.flags.copy()
    if 'fuzzy' in flags:
        flags.remove('fuzzy')
    if 'fuzzy' in strmsg.flags:
        flags.add('fuzzy')
    
    assert len(strmsg.msgstrs) == len(idmsg.msgstrs)
    return Message(idmsg.msgid, strmsg.msgstrs, idmsg.msgid_plural,
                   msgctxt=idmsg.msgctxt, comments=strcomments + idcomments,
                   meta=idmsg.meta, flags=flags)


def merge(msgstrcat, msgidcat, overwrite=True, fname='<unknown>'):
    msgstrdict = msgstrcat.dict()
    newmsgs = []
    for msg in msgidcat:
        if msg.key in msgstrdict:
            msg2 = msgstrdict[msg.key]
            if not msg2.istranslated or len(msg.msgstrs) != len(msg2.msgstrs):
                pass
            elif overwrite or not msg.istranslated:
                msg = merge_msg(msg2, msg)
        newmsgs.append(msg)
    return Catalog(fname, msgidcat.encoding, newmsgs)


@pyg3tmain
def main():
    p = build_parser()
    opts, args = p.parse_args()
    if opts.mode != 'translationproject':
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
    else:
        # mode is 'translationproject'
        msgstrfile = args[0]
        msgidfiles = args[1:]
        strcat = parse(open(msgstrfile))
        for msgidfile in msgidfiles:
            idcat = parse(open(msgidfile))
            if not os.path.exists('merge'):
                os.mkdir('merge')
            if not os.path.isdir('merge'):
                raise IOError('Cannot create directory \'merge\'')
            basefname = os.path.split(msgidfile)[1]
            dstfname = 'merge/%s' % basefname
            dstcat = merge(strcat, idcat, overwrite=True, fname=dstfname)

            idheader = idcat.header
            dstheader = dstcat.header

            def header2dict(header):
                ordered_keys = []
                headerdict = {}
                assert header.msgstr.endswith('\\n')
                for line in header.msgstr.split('\\n')[:-1]:
                    key, value = line.split(': ', 1)
                    ordered_keys.append(key)
                    headerdict[key] = value
                return ordered_keys, headerdict
            
            ordered_keys, dstheaderdict = header2dict(dstheader)
            idheaderdict = header2dict(idheader)[1]

            id_version = basefname.rsplit('.', 2)[0]
            dstheaderdict['Project-Id-Version'] = id_version
            dstheaderdict['POT-Creation-Date'] = \
                idheaderdict['POT-Creation-Date']
            
            newheaderlines = []
            for key in ordered_keys:
                newheaderlines.append(': '.join([key, dstheaderdict[key]]))
            newheaderlines.append('')
            assert not dstheader.hasplurals
            dstheader.msgstrs[0] = '\\n'.join(newheaderlines)

            fd = open(dstfname, 'w')
            for msg in dstcat:
                print >> fd, msg
            fd.close()
