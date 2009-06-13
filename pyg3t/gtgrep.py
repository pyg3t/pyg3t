#!/usr/bin/env python

import sys
import codecs
import re
from itertools import chain, repeat, izip
from optparse import OptionParser

from pyg3t.gtparse import Parser
from pyg3t.util import Colorizer


class GTGrep:
    def __init__(self, msgid_pattern='', msgstr_pattern='',
                 invert_msgid_match=False, invert_msgstr_match=False,
                 ignorecase=True):
        self.msgid_pattern_string = msgid_pattern
        self.msgstr_pattern_string = msgstr_pattern
        flags = 0
        if ignorecase:
            flags |= re.IGNORECASE
        self.msgid_pattern = self.re_compile(msgid_pattern, flags)

        # One should think that we should use re.LOCALE as a compile
        # flag, at least for the msgstr.  This, however, is not the
        # case, because it'll screw up unicode upper/lowercase
        # handling.
        self.msgstr_pattern = self.re_compile(msgstr_pattern, 
                                              flags)
        if invert_msgid_match:
            self.imatch = self.invert
        else:
            self.imatch = bool
        if invert_msgstr_match:
            self.smatch = self.invert
        else:
            self.smatch = bool

    def re_compile(self, pattern, flags=0):
        return re.compile(pattern, re.UNICODE|flags)

    def invert(self, result):
        return not bool(result)

    def check(self, entry):
        imatch = False # whether msgid matches
        smatch = False # whether msgstr matches

        imatch = self.imatch(re.search(self.msgid_pattern, entry.msgid))
        if entry.hasplurals:
            imatch |= self.imatch(re.search(self.msgid_pattern, 
                                            entry.msgid_plural))
        for msgstr in entry.msgstrs:
            smatch |= self.smatch(re.search(self.msgstr_pattern, msgstr))
        return imatch & smatch

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
    parser = OptionParser(usage=usage, description=description)

    parser.add_option('-i', '--msgid', default='', metavar='PATTERN',
                      help='pattern for matching msgid')
    parser.add_option('-s', '--msgstr', default='', metavar='PATTERN',
                      help='pattern for matching msgstr')
    parser.add_option('-I', '--invert-msgid-match', action='store_true',
                      help='invert the sense of matching for msgids')
    parser.add_option('-S', '--invert-msgstr-match', action='store_true',
                      help='invert the sense of matching for msgstrs')
    parser.add_option('-c', '--case', action='store_true',
                      help='use case sensitive matching')
    parser.add_option('-C', '--count', action='store_true',
                      help='print only a count of matching entries')
    parser.add_option('-F', '--fancy', action='store_true',
                      help='use markers to highlight the matching strings')
    parser.add_option('-n', '--line-numbers', action='store_true',
                      help='print line numbers for each entry')
    return parser


def args_iter(args): # open sequentially as needed
    for arg in args:
        yield arg, open(arg, 'r')


def main():
    parser = build_parser()
    opts, args = parser.parse_args()
    
    utf8 = 'UTF-8'
    
    argc = len(args)
    
    multifile_mode = (argc > 1)
    if multifile_mode:
        def print_linenumber(filename, entry):
            print '%s:%d' % (filename, entry.entryline)
    else:
        def print_linenumber(filename, entry):
            print 'Line %d' % entry.entryline

    if argc == 0:
        inputs = iter([('<stdin>', sys.stdin)])
    else:
        inputs = args_iter(args)

    grep = GTGrep(msgid_pattern=opts.msgid.decode(utf8), 
                  msgstr_pattern=opts.msgstr.decode(utf8),
                  invert_msgid_match=opts.invert_msgid_match,
                  invert_msgstr_match=opts.invert_msgstr_match,
                  ignorecase=not opts.case)
    parser = Parser()

    global_matchcount = 0
    for filename, input in inputs:
        entries = parser.parse_asciilike(input)
        matches = grep.search_iter(entries)

        if opts.count:
            nmatches = len(list(matches))
            if opts.fancy:
                # (This is sort of an easter egg)
                colorizer = Colorizer('purple')
                nmatches = colorizer.colorize(str(nmatches))
            print ('%s:' % filename).rjust(40), nmatches
            global_matchcount += nmatches
            continue

        if not opts.fancy:
            for entry in matches:
                if opts.line_numbers:
                    print_linenumber(filename, entry)
                print entry.tostring().encode('utf8')

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
                    print_linenumber(filename, entry)
                # Encode before print ensures there'll be no screwups if stdout
                # has None encoding (in a pipe, for example)
                # Maybe we should wrap stdout with something which recodes
                print string.encode('utf8')

    if opts.count and multifile_mode:
        print 'Found %d matches in %d files' % (global_matchcount, argc)


if __name__ == '__main__':
    main()
