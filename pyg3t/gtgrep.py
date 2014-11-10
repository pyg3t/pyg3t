#!/usr/bin/env python

"""Perform grep-like operations on message catalogs."""

from __future__ import print_function
import sys
import re
from optparse import OptionParser, OptionGroup

from pyg3t import __version__
from pyg3t.gtparse import parse
from pyg3t.util import Colorizer, pyg3tmain, Encoder


class GTGrep:
    def __init__(self, msgid_pattern=None, msgstr_pattern=None,
                 msgctxt_pattern=None, comment_pattern=None,
                 imsgid_pattern=None, imsgstr_pattern=None,
                 imsgctxt_pattern=None, icomment_pattern=None,
                 ignorecase=True, filterpattern=None,
                 match_all=True):

        flags = 0
        if ignorecase:
            flags |= re.IGNORECASE
        
        # One should think that we should use re.LOCALE as a compile
        # flag, at least for the msgstr.  This, however, is not the
        # case, because it'll screw up unicode upper/lowercase
        # handling.

        def re_compile(pattern, name):
            try:
                return re.compile(pattern, re.UNICODE|flags)
            except re.error, err:
                raise re.error('bad %s pattern "%s": %s' % (name, pattern,
                                                            err))
        
        if filterpattern is None:
            def filter(string):
                return string
        else:
            def filter(string):
                return filterpattern.sub('', string)
        self.filter = filter

        tests = []
        inversetests = []
        
        def search(pattern, string):
            return pattern.search(self.filter(string))

        class Test:
            def __init__(self, pattern):
                self.pattern = pattern

            def check(self, msg):
                pass # override

        def checkid(pattern, msg):
            if search(pattern, msg.msgid):
                return True
            if msg.hasplurals and search(pattern, msg.msgid_plural):
                return True
            return False

        def checkstr(pattern, msg):
            for msgstr in msg.msgstrs:
                if search(pattern, msgstr):
                    return True
            return False

        def checkcomments(pattern, msg):
            for comment in msg.comments:
                if search(pattern, comment):
                    return True
            return False
        
        def checkctxt(pattern, msg):
            return msg.has_context and search(pattern, msg.msgctxt)

        class Check:
            def __init__(self, checkfunc, pattern, name):
                self.checkfunc = checkfunc
                self.pattern = re_compile(pattern, name)
                
            def __call__(self, msg):
                return self.checkfunc(self.pattern, msg)

        if msgid_pattern is not None:
            tests.append(Check(checkid, msgid_pattern, '--msgid'))
        if imsgid_pattern is not None:
            inversetests.append(Check(checkid, imsgid_pattern, '--imsgid'))
        if msgstr_pattern is not None:
            tests.append(Check(checkstr, msgstr_pattern, '--msgstr'))
        if imsgstr_pattern is not None:
            inversetests.append(Check(checkstr, imsgstr_pattern, '--imsgstr'))
        if comment_pattern is not None:
            tests.append(Check(checkcomments, comment_pattern, '--comment'))
        if icomment_pattern is not None:
            inversetests.append(Check(checkcomments, icomment_pattern,
                                  '--icomment'))
        if msgctxt_pattern is not None:
            tests.append(Check(checkctxt, msgctxt_pattern, '--msgctxt'))
        if imsgctxt_pattern is not None:
            inversetests.append(Check(checkctxt, imsgctxt_pattern,
                                      '--imsgctxt'))
        
        if match_all:
            def check(msg):
                for test in inversetests:
                    if test(msg):
                        return False
                for test in tests:
                    if not test(msg):
                        return False
                return True
        else: # match any
            def check(msg):
                for test in inversetests:
                    if test(msg):
                        return False
                for test in tests:
                    if test(msg):
                        return True
                return False

        self._check = check

    def check(self, msg):
        #return self._check(msg.decode())
        return self._check(msg)
    
    def search_iter(self, msgs):
        for msg in msgs:
            matches = self.check(msg)
            if matches:
                yield msg


def build_parser():
    description = ('Print po-FILE messages for which original or translated '
                   'strings match a particular pattern.  '
                   'If no FILE is provided, read from stdin.')

    usage = '%prog [OPTIONS] [PATTERN] [FILE...]'
    parser = OptionParser(usage=usage, description=description,
                          version=__version__)
    
    match = OptionGroup(parser, 'Matching options')
    output = OptionGroup(parser, 'Output options')
    
    match.add_option('-i', '--msgid', metavar='PATTERN',
                     help='pattern for matching msgid')
    match.add_option('-I', '--imsgid', metavar='PATTERN',
                     help='pattern for inverse matching of msgid')
    match.add_option('-s', '--msgstr', metavar='PATTERN',
                     help='pattern for matching msgstr')
    match.add_option('-S', '--imsgstr', metavar='PATTERN',
                     help='pattern for inverse matching of msgstr')
    match.add_option('--msgctxt', metavar='PATTERN',
                     help='pattern for matching msgctxt')
    match.add_option('--imsgctxt', metavar='PATTERN',
                     help='pattern for inverse matching of msgctxt')
    match.add_option('--comment', metavar='PATTERN',
                     help='pattern for matching comments')
    match.add_option('--icomment', metavar='PATTERN',
                     help='pattern for inverse matching of comments')
    match.add_option('-c', '--case', action='store_true',
                     help='use case sensitive matching')
    match.add_option('-f', '--filter', action='store_true', 
                     help='ignore filtered characters when matching')
    match.add_option('--filtered-chars', metavar='CHARS', default='_&',
                     help='string of characters that are ignored when'
                     ' given the --filter option.  Default: %default')
    
    output.add_option('-C', '--count', action='store_true',
                      help='print only a count of matching messages')
    output.add_option('-F', '--fancy', action='store_true',
                      help='use markers to highlight the matching strings')
    output.add_option('-n', '--line-numbers', action='store_true',
                      help='print line numbers for each message')
    output.add_option('-G', '--gettext-compatible', action='store_true',
                      help='print annotations such as line numbers as'
                      ' comments, making output a valid po-file.')
    
    parser.add_option_group(match)
    parser.add_option_group(output)
    
    return parser


def args_iter(args, parser): # open sequentially as needed
    for arg in args:
        try:
            fd = open(arg, 'r')
        except IOError, err:
            parser.error(err)
        yield arg, fd


@pyg3tmain
def main():
    parser = build_parser()
    opts, args = parser.parse_args()
    
    charset = 'UTF-8' # yuck
    out = Encoder(sys.stdout, charset)
    
    patterns = {}
    keys = ['msgid', 'msgstr', 'msgctxt', 'comment']
    negative_keys = ['i' + key for key in keys]
    for key in keys + negative_keys:
        pattern = getattr(opts, key)
        if pattern is not None:
            patterns[key] = pattern.decode(charset)
    
    match_all = True
    
    if not patterns:
        try:
            pattern = args.pop(0).decode(charset)
        except IndexError:
            parser.error('No PATTERNs given')
            raise SystemExit(17)
        else:
            patterns['msgid'] = pattern
            patterns['msgstr'] = pattern
            patterns['msgctxt'] = pattern
            patterns['comment'] = pattern
            match_all = False

    argc = len(args)
    
    multifile_mode = (argc > 1)
    if multifile_mode:
        def format_linenumber(filename, msg):
            return '%s:%d' % (filename, msg.meta['lineno'])
    else:
        def format_linenumber(filename, msg):
            return 'Line %d' % msg.meta['lineno']

    if opts.gettext_compatible:
        orig_fmt_lineno = format_linenumber
        def format_linenumber(filename, msg):
            return '# pyg3t: %s' % orig_fmt_lineno(filename, msg)

    if argc == 0:
        inputs = iter([('<stdin>', sys.stdin)])
    else:
        inputs = args_iter(args, parser)

    filterpattern = None
    if opts.filter:
        try:
            filterpattern = re.compile('[%s]' % opts.filtered_chars)
        except re.error, err:
            parser.error('Bad filter pattern "%s": %s' % (opts.filtered_chars,
                                                          err))

    try:
        grep = GTGrep(msgid_pattern=patterns.get('msgid'),
                      imsgid_pattern=patterns.get('imsgid'),
                      msgstr_pattern=patterns.get('msgstr'),
                      imsgstr_pattern=patterns.get('imsgstr'),
                      msgctxt_pattern=patterns.get('msgctxt'),
                      imsgctxt_pattern=patterns.get('imsgctxt'),
                      comment_pattern=patterns.get('comment'),
                      icomment_pattern=patterns.get('icomment'),
                      ignorecase=not opts.case,
                      filterpattern=filterpattern,
                      match_all=match_all)
    except re.error, err:
        parser.error(err)

    global_matchcount = 0
    for filename, input in inputs:
        cat = parse(input)
        matches = grep.search_iter(cat)

        if opts.count:
            nmatches = len(list(matches))
            if opts.fancy:
                # (This is sort of an easter egg)
                colorizer = Colorizer('purple')
                nmatches_str = colorizer.colorize(str(nmatches))
            else:
                nmatches_str = str(nmatches)
            print(('%s:' % filename).rjust(40), nmatches_str, file=out)
            global_matchcount += nmatches
            continue

        if not opts.fancy:
            for msg in matches:
                if opts.line_numbers:
                    print(format_linenumber(filename, msg), file=out)
                elif multifile_mode:
                    print('File:', filename, file=out)
                print(msg.tostring(), file=out)

        if opts.fancy:
            # It's a bit hairy to do this properly, so we'll just make a hack
            # where every instance of the matching strings (not just those in
            # the matched msgid or msgstr) are colored

            class MatchColorizer(Colorizer):
                def colorize_match(self, match_object):
                    matchstring = match_object.group()
                    return self.colorize(matchstring)

            highlighter = MatchColorizer('light blue')
            
            match_highlight_pattern = u'|'.join([pattern
                                                 for pattern
                                                 in patterns.values()])
            match_highlight_pattern = re.compile(match_highlight_pattern)

            for msg in matches:
                string = msg.tostring()
                string = re.sub(match_highlight_pattern, 
                                highlighter.colorize_match, string)
                
                if opts.line_numbers:
                    print(format_linenumber(filename, msg), file=out)
                # Encode before print ensures there'll be no screwups if stdout
                # has None encoding (in a pipe, for example)
                # Maybe we should wrap stdout with something which recodes
                print(string, file=out)

    if opts.count and multifile_mode:
        print('Found %d matches in %d files' % (global_matchcount, argc),
              file=out)
