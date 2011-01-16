#!/usr/bin/env python

"""Perform grep-like operations on message catalogs."""

import sys
import re
from optparse import OptionParser, OptionGroup
import operator

from pyg3t import __version__
from pyg3t.gtparse import Parser
from pyg3t.util import Colorizer


class NullFilter:
    def filter(self, string):
        return string

class SubstitutionFilter:
    def __init__(self, pattern):
        self.pattern = pattern

    def filter(self, string):
        return re.sub(self.pattern, '', string)


class GTGrep:
    def __init__(self, msgid_pattern='', msgstr_pattern='',
                 comment_pattern='',
                 invert_msgid_match=False, invert_msgstr_match=False,
                 ignorecase=True, filter=None, boolean_operator=None):
        self.msgid_pattern_string = msgid_pattern
        self.msgstr_pattern_string = msgstr_pattern
        self.comment_pattern_string = comment_pattern
        
        flags = 0
        if ignorecase:
            flags |= re.IGNORECASE
        try:
            self.msgid_pattern = self.re_compile(msgid_pattern, flags)
        except re.error, err:
            raise re.error('bad msgid pattern "%s": %s' % (msgid_pattern, err))

        # One should think that we should use re.LOCALE as a compile
        # flag, at least for the msgstr.  This, however, is not the
        # case, because it'll screw up unicode upper/lowercase
        # handling.
        try:
            self.msgstr_pattern = self.re_compile(msgstr_pattern, flags)
        except re.error, err:
            raise re.error('bad msgstr pattern "%s": %s' % (msgstr_pattern, 
                                                            err))
        try:
            self.comment_pattern = self.re_compile(comment_pattern, flags)
        except re.error, err:
            raise re.error('bad comment pattern "%s": %s' % (comment_pattern,
                                                             err))


        if invert_msgid_match:
            self.imatch = self.invert
        else:
            self.imatch = bool
        if invert_msgstr_match:
            self.smatch = self.invert
        else:
            self.smatch = bool

        if filter is None:
            filter = NullFilter()
        self.filter = filter

        if boolean_operator is None:
            boolean_operator = operator.and_
        self.boolean_operator = boolean_operator

    def re_compile(self, pattern, flags=0):
        return re.compile(pattern, re.UNICODE|flags)
    
    def invert(self, result):
        return not bool(result)

    def check(self, entry):
        imatch = False # whether msgid matches
        smatch = False # whether msgstr matches

        filter = self.filter.filter

        imatch = self.imatch(re.search(self.msgid_pattern, 
                                       filter(entry.msgid)))
        if entry.hasplurals:
            imatch |= self.imatch(re.search(self.msgid_pattern, 
                                            filter(entry.msgid_plural)))
        for msgstr in entry.msgstrs:
            smatch |= self.smatch(re.search(self.msgstr_pattern, 
                                            filter(msgstr)))
        return self.boolean_operator(imatch, smatch)

    def search_iter(self, entries):
        for entry in entries:
            matches = self.check(entry)
            if matches:
                yield entry


def build_parser():
    description = ('Print po-FILE entries for which original or translated '
                   'strings match a particular pattern.  '
                   'If no FILE is provided, read from stdin.')

    usage = '%prog [OPTIONS] [FILE]'
    parser = OptionParser(usage=usage, description=description,
                          version=__version__)
    
    match = OptionGroup(parser, 'Matching options')
    output = OptionGroup(parser, 'Output options')
    
    match.add_option('-i', '--msgid', default='', metavar='PATTERN',
                     help='pattern for matching msgid')
    match.add_option('-s', '--msgstr', default='', metavar='PATTERN',
                     help='pattern for matching msgstr')
    match.add_option('--comment', default='', metavar='PATTERN',
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
                      help='print only a count of matching entries')
    output.add_option('-F', '--fancy', action='store_true',
                      help='use markers to highlight the matching strings')
    output.add_option('-n', '--line-numbers', action='store_true',
                      help='print line numbers for each entry')
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
    
    utf8 = 'UTF-8'
    
    msgid_pattern = opts.msgid.decode(utf8)
    msgstr_pattern = opts.msgstr.decode(utf8)
    comment_pattern = opts.comment.decode(utf8)
    boolean_operator = None
    if msgid_pattern == msgstr_pattern == '':
        try:
            msgid_pattern = msgstr_pattern = args.pop(0).decode(utf8)
        except IndexError:
            print >> sys.stderr, 'No pattern, no files'
            raise SystemExit(17)
        else:
            boolean_operator = operator.or_

    argc = len(args)
    
    multifile_mode = (argc > 1)
    if multifile_mode:
        def format_linenumber(filename, entry):
            return '%s:%d' % (filename, entry.entryline)
    else:
        def format_linenumber(filename, entry):
            return 'Line %d' % entry.entryline

    if opts.gettext_compatible:
        orig_fmt_lineno = format_linenumber
        def format_linenumber(filename, entry):
            return '# pyg3t: %s' % orig_fmt_lineno(filename, entry)

    if argc == 0:
        inputs = iter([('<stdin>', sys.stdin)])
    else:
        inputs = args_iter(args, parser)

    filter = None
    if opts.filter:
        try:
            pattern = re.compile('[%s]' % opts.filtered_chars)
        except re.error, err:
            parser.error('Bad filter pattern "%s": %s' % (opts.filtered_chars,
                                                          err))
        filter = SubstitutionFilter(pattern)

    try:
        grep = GTGrep(msgid_pattern=msgid_pattern,
                      msgstr_pattern=msgstr_pattern,
                      comment_pattern=comment_pattern,
                      invert_msgid_match=opts.invert_msgid_match,
                      invert_msgstr_match=opts.invert_msgstr_match,
                      ignorecase=not opts.case, 
                      filter=filter,
                      boolean_operator=boolean_operator)
    except re.error, err:
        parser.error(err)
    parser = Parser()

    global_matchcount = 0
    for filename, input in inputs:
        entries = parser.parse(input)
        matches = grep.search_iter(entries)

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
            for entry in matches:
                if opts.line_numbers:
                    print format_linenumber(filename, entry)
                elif multifile_mode:
                    print 'File:', filename
                print entry.tostring()#.encode('utf8')

        if opts.fancy:
            # It's a bit hairy to do this properly, so we'll just make a hack
            # where every instance of the matching strings (not just those in
            # the matched msgid or msgstr) are colored

            class MatchColorizer(Colorizer):
                def colorize_match(self, match_object):
                    matchstring = match_object.group()
                    return self.colorize(matchstring)

            ihighlighter = MatchColorizer('light blue')
            shighlighter = MatchColorizer('light green')

            for entry in matches:
                string = entry.tostring()
                if grep.msgid_pattern_string:
                    string = re.sub(grep.msgid_pattern,
                                    ihighlighter.colorize_match, 
                                    string)
                if grep.msgstr_pattern_string:
                    string = re.sub(grep.msgstr_pattern,
                                    shighlighter.colorize_match,
                                    string)

                if opts.line_numbers:
                    print format_linenumber(filename, entry)
                # Encode before print ensures there'll be no screwups if stdout
                # has None encoding (in a pipe, for example)
                # Maybe we should wrap stdout with something which recodes
                print string.encode('utf8')

    if opts.count and multifile_mode:
        print 'Found %d matches in %d files' % (global_matchcount, argc)


if __name__ == '__main__':
    main()
