#!/usr/bin/env python

"""Perform grep-like operations on message catalogs."""

import sys
import re
from optparse import OptionParser, OptionGroup

from pyg3t import __version__
from pyg3t.gtparse import parse
from pyg3t.util import Colorizer


class GTGrep:
    def __init__(self, msgid_pattern=None, msgstr_pattern=None,
                 msgctxt_pattern=None, comment_pattern=None,
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
                raise re.error('bad %s pattern "%s": %s' % (name,
                                                            pattern,
                                                            err))
        
        if filterpattern is None:
            def filter(string):
                return string
        else:
            def filter(string):
                return filterpattern.sub('', string)
        self.filter = filter

        tests = []
        
        def search(pattern, string):
            return pattern.search(self.filter(string))
        
        if msgid_pattern is not None:
            msgid_pattern = re_compile(msgid_pattern, 'msgid')
            def checkmsgid(msg):
                if search(msgid_pattern, msg.msgid):
                    return True
                if msg.hasplurals and search(msgid_pattern,
                                             msg.msgid_plural):
                    return True
                return False
            tests.append(checkmsgid)
        
        if msgstr_pattern is not None:
            msgstr_pattern = re_compile(msgstr_pattern, 'msgstr')
            def checkmsgstr(msg):
                for msgstr in msg.msgstrs:
                    if search(msgstr_pattern, msgstr):
                        return True
                return False
            tests.append(checkmsgstr)
        
        if comment_pattern is not None:
            comment_pattern = re_compile(comment_pattern, 'comment')
            def checkcomments(msg):
                for comment in msg.comments:
                    if search(comment_pattern, comment):
                        return True
                return False
            tests.append(checkcomments)
        
        if msgctxt_pattern is not None:
            msgctxt_pattern = re_compile(msgctxt_pattern, 'msgctxt')
            def checkmsgctxt(msg):
                return msg.has_context and search(msgctxt_pattern, 
                                                  msg.msgctxt)
            tests.append(checkmsgctxt)
        
        if match_all:
            def check(msg):
                for test in tests:
                    if not test(msg):
                        return False
                return True
        else: # match any
            def check(msg):
                for test in tests:
                    if test(msg):
                        return True
                return False

        self._check = check

    def check(self, msg):
        return self._check(msg.decode())
    
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
    match.add_option('-s', '--msgstr', metavar='PATTERN',
                     help='pattern for matching msgstr')
    match.add_option('--msgctxt', metavar='PATTERN',
                     help='pattern for matching msgctxt')
    match.add_option('--comment', metavar='PATTERN',
                     help='pattern for matching comments')
    
    match.add_option('-I', '--invert-msgid-match', action='store_true',
                     help='invert the sense of matching for msgids')
    match.add_option('-S', '--invert-msgstr-match', action='store_true',
                     help='invert the sense of matching for msgstrs')
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

def main():
    parser = build_parser()
    opts, args = parser.parse_args()
    
    charset = 'UTF-8' # yuck
    
    patterns = {}
    for key in ['msgid', 'msgstr', 'msgctxt', 'comment']:
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

    if opts.invert_msgid_match and 'msgid' in patterns:
        patterns['msgid'] = '(?!%s)' % patterns['msgid']
    if opts.invert_msgstr_match and 'msgstr' in patterns:
        patterns['msgstr'] = '(?!%s)' % patterns['msgstr']
    
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
                      msgstr_pattern=patterns.get('msgstr'),
                      msgctxt_pattern=patterns.get('msgctxt'),
                      comment_pattern=patterns.get('comment'),
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
            print ('%s:' % filename).rjust(40), nmatches_str
            global_matchcount += nmatches
            continue

        if not opts.fancy:
            for msg in matches:
                if opts.line_numbers:
                    print format_linenumber(filename, msg)
                elif multifile_mode:
                    print 'File:', filename
                print msg.tostring()

        if opts.fancy:
            # It's a bit hairy to do this properly, so we'll just make a hack
            # where every instance of the matching strings (not just those in
            # the matched msgid or msgstr) are colored

            class MatchColorizer(Colorizer):
                def colorize_match(self, match_object):
                    matchstring = match_object.group()
                    return self.colorize(matchstring)

            highlighter = MatchColorizer('light blue')
            
            match_highlight_pattern = u'|'.join([comment_pattern,
                                                 msgctxt_pattern,
                                                 msgid_pattern,
                                                 msgstr_pattern])
            match_highlight_pattern = re.compile(match_highlight_pattern)

            for msg in matches:
                string = msg.tostring()
                string = re.sub(match_highlight_pattern, 
                                highlighter.colorize_match, string)
                
                if opts.line_numbers:
                    print format_linenumber(filename, msg)
                # Encode before print ensures there'll be no screwups if stdout
                # has None encoding (in a pipe, for example)
                # Maybe we should wrap stdout with something which recodes
                print string

    if opts.count and multifile_mode:
        print 'Found %d matches in %d files' % (global_matchcount, argc)


if __name__ == '__main__':
    main()
