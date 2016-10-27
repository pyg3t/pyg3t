from __future__ import print_function, unicode_literals
import os
from io import StringIO, BytesIO
from optparse import OptionParser, OptionGroup

from pyg3t.gtparse import parse, iparse, Message, Catalog
from pyg3t.util import (pyg3tmain, ansi, noansi,
                        get_encoded_output, get_bytes_input, get_bytes_output)
from pyg3t.gtwdiff import MSGDiffer, print_msg_diff


def build_parser():
    usage = ('Usage: %prog [OPTION...] MSGSTR_FILE MSGID_FILE...\n'
             '       %prog [OPTION...] --annotations FILE')

    p = OptionParser(usage=usage,
                     description='Combine msgstrs from MSGSTR_FILE with '
                     'msgids from MSGID_FILEs where applicable, printing '
                     'the resulting catalog to stdout.  The result is '
                     'guaranteed to be template-compatible with MSGID_FILE.')
    #p.add_option('--msgmerge', action='store_true', # XXX temporarily disabled
    #             help='use msgmerge for fuzzy matching.')
    mode_opts = OptionGroup(p, 'Merge modes')

    modes = ['left', 'right', 'translationproject', 'annotations']
    #, 'launchpad', 'versionport']
    text = {'left': ('prefer translations from MSGSTR_FILE in conflicts '
                     '(default).'),
            'right': 'prefer translations from MSGID_FILE in conflicts.',
            'translationproject': ('merge MSGSTR_FILE into all MSGID_FILES '
                                   'and write to separate files.  '
                                   'Useful for merging to many '
                                   'older versions on translationproject.org'),
            'annotations': ('substitute messages from FILE into files.  '
                            'Messages must have pyg3t annotations as '
                            'generated by the --annotate option that some '
                            'pyg3t tools support.')}
            #'launchpad': ('transfer as many strings as possible, '
            #              'keeping header of MSGID_FILE '
            #              'compatible with upload to Launchpad.')}
    #'versionport': ('transfer as many strings as possible, '
    #           'but update header to contain ... blahblah') # TODO implement
    for mode in modes:
        mode_opts.add_option('--%s' % mode, action='store_const',
                             default=modes[0],
                             dest='mode', const=mode, help=text[mode])
    p.add_option_group(mode_opts)
    # option: translation project version merge mode
    # option: launchpad upload prepare mode

    #p.add_option('--keep-header', action='store_true',
    #             help='')
    p.add_option('--overwrite', action='store_true',
                 help='in --annotation mode, write updates back to files.')
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


def merge_translation_project(opts, args):
    assert opts.mode == 'translationproject'
    msgstrfile = args[0]
    msgidfiles = args[1:]
    strcat = parse(get_bytes_input(msgstrfile))
    for msgidfile in msgidfiles:
        idcat = parse(get_bytes_input(msgidfile))
        if not os.path.exists('merge'):
            os.mkdir('merge')
        if not os.path.isdir('merge'):
            raise IOError('Cannot create directory \'merge\'')
        basefname = os.path.split(msgidfile)[1]
        dstfname = 'merge/%s' % basefname
        dstcat = merge(strcat, idcat, overwrite=True, fname=dstfname)

        idheader = idcat.msgs[0]
        dstheader = dstcat.msgs[0]

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
        assert not dstheader.isplural
        dstheader.msgstrs[0] = r'\n'.join(newheaderlines)

        fd = get_encoded_output(idcat.encoding, dstfname)
        for msg in dstcat:
            print(msg.tostring(), file=fd)
        fd.close()

def merge_by_annotations(parser, opts, args):
    from pyg3t.annotate import strip_annotations
    from collections import OrderedDict

    out = get_encoded_output('utf-8')

    if len(args) != 1:
        parser.error('Annotation merge mode accepts only one FILE.  Got %d'
                     % len(args))
    inputfname = args[0]

    differ = MSGDiffer()

    msgs_by_outfile = OrderedDict()

    for msg in iparse(get_bytes_input(inputfname), obsolete=False,
                      trailing=False):
        annotations, outfname, lineno = strip_annotations(msg)
        if outfname is None:
            assert msg.msgid == '', msg.msgid
            continue

        if not msg.istranslated:
            continue

        msg.meta['lineno'] = lineno
        msgs_by_outfile.setdefault(outfname, []).append(msg)

    nupdates_total = 0

    for fname, new_msgs in msgs_by_outfile.items():
        new_dict = {}
        for msg in new_msgs:
            assert not msg.key in new_dict
            new_dict[msg.key] = msg

        fd = get_bytes_input(fname)
        old_cat = iparse(fd)

        buf = StringIO()

        nupdates_thisfile = 0
        nmsgs_thisfile = 0
        old_encoding = None
        for old_msg in old_cat:
            if old_encoding is None:
                assert old_msg.msgid == ''
                old_encoding = old_msg.meta['encoding']

            if old_msg.key in new_dict:
                assert new_dict[old_msg.key].istranslated
                # XXX What if we should merge a header?
                new_msg = new_dict.pop(old_msg.key)
                assert new_msg.msgid == old_msg.msgid
                assert new_msg.msgctxt == old_msg.msgctxt

                print(ansi.light_blue('--- %s ---' % fd.name), file=out)
                print_msg_diff(differ, old_msg, new_msg, out)
                nupdates_thisfile += 1
                nupdates_total += 1
                msg = new_msg
            else:
                msg = old_msg

            nmsgs_thisfile += 1
            print(msg.tostring(), file=buf)

        fd.close()  # Close so we can (perhaps) overwrite it in a moment

        if nupdates_thisfile == 0:
            continue

        #assert len(new_dict) == 0  # All should have been popped now
        # Actually there may be untranslated ones; those would be left.
        # For now, new_dict may not be empty after all

        txt = buf.getvalue()
        btxt = txt.encode(old_encoding)

        check_buf = BytesIO()
        check_buf.write(btxt)
        check_buf.seek(0)
        extra_secure_check_cat = list(iparse(check_buf))
        assert len(extra_secure_check_cat) == nmsgs_thisfile

        if opts.overwrite:
            print(ansi.light_red('>>> Updating %s <<<' % fname), file=out)
            with get_bytes_output(fname) as outfd:
                print(btxt, file=outfd)
        else:
            if nupdates_thisfile == 1:
                template = '%d update applied to %s'
            else:
                template = '%d updates applied to %s'
            print(ansi.light_green(template % (nupdates_thisfile, fname)),
                  file=out)

            if not os.path.isdir('merge'):
                os.mkdir('merge')

            outfname = 'merge/%s' % os.path.basename(fname)
            with get_bytes_output(outfname) as outfd:
                print(btxt, file=outfd)
            print(ansi.light_green('Written to %s' % outfname))

        print(file=out)

    if opts.overwrite:
        sentence_start = 'Updated'
        color = ansi.yellow
    else:
        sentence_start = 'Updates applied to'
        color = ansi.light_green

    messages_word = 'message' if nupdates_total == 1 else 'messages'
    files_word = 'file' if len(msgs_by_outfile) == 1 else 'files'

    statusmsg = ('{action} {nmsgs} {messages} in {nfiles} {files}.'
                 .format(action=sentence_start, nmsgs=nupdates_total,
                         messages=messages_word,
                         nfiles=len(msgs_by_outfile), files=files_word))
    print(color(statusmsg), file=out)


@pyg3tmain(build_parser)
def main(parser):
    opts, args = parser.parse_args()

    if opts.mode != 'annotations' and opts.overwrite:
        parser.error('--write can only be used with --annotations')

    if opts.mode == 'translationproject':
        merge_translation_project(opts, args)
    elif opts.mode == 'annotations':
        merge_by_annotations(parser, opts, args)
    else:
        if len(args) != 2:
            parser.error('Expected two arguments, got %d' % len(args))
        fname1, fname2 = args

        #if opts.msgmerge:
        #    msgmerge = Popen(['msgmerge', fname1, fname2],
        #                     stdout=PIPE,
        #                     stderr=PIPE)
        #    cat1 = parse(msgmerge.stdout) # XXX encoding??
        #else:
        cat1 = parse(open(fname1, 'rb'))
        cat2 = parse(open(fname2, 'rb'))

        if opts.mode == 'left':
            overwrite = True
        else:
            assert opts.mode == 'right'
            overwrite = False
            # more complicated modes?

        cat = merge(cat1, cat2, overwrite)
        out = get_encoded_output(cat.encoding)
        for msg in cat:
            print(msg.tostring(), file=out)
        #for line in cat1.obsoletes:
        #    print line, # keep which obsoletes?
        # obsoletes must also be unique, and must not clash with existing msgs
