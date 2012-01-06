#!/usr/bin/env python

"""Perform grep-like operations on message catalogs."""

import sys
import re
from optparse import OptionParser, OptionGroup

from pyg3t import __version__
from pyg3t.gtparse import parse
from pyg3t.util import Colorizer


class GTGrep:
    def __init__(self, msgid_pattern='', msgstr_pattern='',
                 msgctxt_pattern='', comment_pattern='',
                 ignorecase=True, filterpattern=None):

        self.patterns = dict(msgid=msgid_pattern,
                             msgstr=msgstr_pattern,
                             msgctxt=msgctxt_pattern,
                             comment=comment_pattern)
        
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
        
        self.msgstr_pattern = re_compile(msgstr_pattern, 'msgstr')
        self.msgid_pattern = re_compile(msgid_pattern, 'msgid')
        self.msgctxt_pattern = re_compile(msgctxt_pattern, 'msgctxt')
        self.comment_pattern = re_compile(comment_pattern, 'comment')

        if filterpattern is None:
            def filter(string):
                return string
        else:
            def filter(string):
                return filter.sub('', string)
        self.filter = filter
    
    def check(self, msg):
        msg = msg.decode()
        
        def search(pattern, string):
            return re.search(pattern, self.filter(string))
        
        for comment in msg.comments:
            if search(self.comment_pattern, comment):
                return True
        
        if msg.has_context and search(self.msgctxt_pattern, msg.msgctxt):
            return True
        
        if search(self.msgid_pattern, msg.msgid):
            return True
        
        if msg.hasplurals and search(self.msgid_pattern, msg.msgid_plural):
            return True
        
        for msgstr in msg.msgstrs:
            if search(self.msgstr_pattern, msgstr):
                return True
        
        return False

    def search_iter(self, msgs):
        for msg in msgs:
            matches = self.check(msg)
            if matches:
                yield msg


def build_parser():
    description = ('Print po-FILE messages for which original or translated '
                   'strings match a particular pattern.  '
                   'If no FILE is provided, read from stdin.')

    usage = '%prog [OPTIONS] [FILE]'
    parser = OptionParser(usage=usage, description=description,
                          version=__version__)
    
    match = OptionGroup(parser, 'Matching options')
    output = OptionGroup(parser, 'Output options')
    
    match.add_option('-i', '--msgid', default=MATCH_NOTHING, metavar='PATTERN',
                     help='pattern for matching msgid')
    match.add_option('-s', '--msgstr', default=MATCH_NOTHING, 
                     metavar='PATTERN',
                     help='pattern for matching msgstr')
    match.add_option('--msgctxt', default=MATCH_NOTHING, metavar='PATTERN',
                     help='pattern for matching msgctxt')
    match.add_option('--comment', default=MATCH_NOTHING, metavar='PATTERN',
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

MATCH_NOTHING = '(?!)'

def main():
    parser = build_parser()
    opts, args = parser.parse_args()
    
    charset = 'UTF-8' # yuck
    
    msgid_pattern = opts.msgid.decode(charset)
    msgstr_pattern = opts.msgstr.decode(charset)
    msgctxt_pattern = opts.msgctxt.decode(charset)
    comment_pattern = opts.comment.decode(charset)
    
    if not any(pattern != MATCH_NOTHING for pattern in [msgid_pattern,
                                                        msgstr_pattern,
                                                        msgctxt_pattern,
                                                        comment_pattern]):
        try:
            pattern = args.pop(0).decode(charset)
        except IndexError:
            print >> sys.stderr, 'No pattern, no files'
            raise SystemExit(17)
        else:
            msgid_pattern = pattern
            msgstr_pattern = pattern
            msgctxt_pattern = pattern
            comment_pattern = pattern
    
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

    if opts.invert_msgid_match:
        msgid_pattern = '(?!%s)' % msgid_pattern
    if opts.invert_msgstr_match:
        msgstr_pattern = '(?!%s)' % msgstr_pattern

    try:
        grep = GTGrep(msgid_pattern=msgid_pattern,
                      msgstr_pattern=msgstr_pattern,
                      msgctxt_pattern=msgctxt_pattern,
                      comment_pattern=comment_pattern,
                      ignorecase=not opts.case,
                      filterpattern=filterpattern)
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
            
            match_any = u'|'.join([comment_pattern,
                                   msgctxt_pattern,
                                   msgid_pattern,
                                   msgstr_pattern])
            any_pattern = re.compile(match_any)

            for msg in matches:
                string = msg.tostring()
                string = re.sub(match_any, highlighter.colorize_match, string)
                
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
