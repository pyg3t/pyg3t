#!/usr/bin/env python

import sys
import fileinput
import itertools
from optparse import OptionParser

from pyg3t.gtparse import Parser
from pyg3t.gtxml import GTXMLChecker
from pyg3t import __version__
import xml.sax

# TODO: convention checks (quotation marks?)

def is_translatorcredits(msgid):
    return msgid in ['translator-credits', 'translator_credits']


class PartiallyTranslatedPluralTest:
    def check(self, entry, msgid, msgstr):
        warn = None
        if msgstr == '':
            warn = 'Some plurals not translated'
        return msgid, msgstr, warn


class XMLTest:
    def __init__(self):
        self.checker = GTXMLChecker()

    def check(self, entry, msgid, msgstr):
        warn = None
        try:
            self.checker.check_entry(entry)
        except xml.sax.SAXParseException, err:
            warn = 'Invalid xml: ' + str(err)
        return msgid, msgstr, warn


class WordRepeatTest:
    def check(self, entry, msgid, msgstr):
        words = msgstr.split()
        for word1, word2 in zip(words[:-1], words[1:]):
            if word1.isalpha() and word1 == word2:
                warn = 'Repeated word: "%s"' % word1
                return msgid, msgstr, warn
        return msgid, msgstr, None

class ContextCharTest:
    def __init__(self, context_char):
        self.context_char = context_char

    def check(self, entry, msgid, msgstr):
        index1 = msgid.find(self.context_char)
        warn = None
        if index1 == -1:
            return msgid, msgstr, warn

        msgid = msgid[index1 + len(self.context_char):]
        index2 = msgstr.find(self.context_char)
        if index2 != -1:
            warn = 'Context character "%s" found in msgstr' % self.context_char
            msgstr = msgstr[index2 + len(self.context_char):]
        return msgid, msgstr, warn


def sametype(msgid, msgstr):
    for n, (ichar, schar) in enumerate(itertools.izip(msgid, msgstr)):
        if ichar.isalpha() and schar.isalpha():
            return True, n
        if ichar != schar:
            return False, n
    return True, n

        
def samecase(self, a, b): # ugly
    if not msgid or not msgstr:
        return msgid, msgstr, None
    issametype, n = sametype(self, msgid, msgstr)
    if n > 0 or not issametype:
        return issametype

    ichar = msgid[0]
    schar = msgstr[0]
    if ichar.isalpha() and schar.isalpha():
        return a.isupper() == schar.isupper()
    return False
        

class LeadingCharTest:
    def check(self, entry, msgid, msgstr):
        if not msgid or not msgstr:
            return msgid, msgstr, None
        ichar = msgid[0]
        schar = msgstr[0]
        if ichar.isalpha() and schar.isalpha():
            if ichar.isupper() == schar.isupper():
                return msgid, msgstr, None
            else:
                return msgid, msgstr, 'Leading character case mismatch'

        issametype, index = sametype(msgid, msgstr)
        if issametype:
            return msgid, msgstr, None
        else:
            return msgid, msgstr, 'Leading character type mismatch'


class TrailingCharTest:
    def check(self, entry, msgid, msgstr):
        if not msgid or not msgstr:
            return msgid, msgstr, None
        issametype, index = sametype(reversed(msgid), 
                                     reversed(msgstr))
        if issametype:
            return msgid, msgstr, None
        else:
            if msgid[-1 - index:].isspace() or msgstr[-1 - index:].isspace():
                warn = 'Trailing whitespace inconsistency'
            else:
                warn = 'Inconsistent punctuation'
            return msgid, msgstr, warn


class AcceleratorTest:
    def __init__(self, accel_key):
        self.accel_key = accel_key

    def check(self, entry, msgid, msgstr):
        char = self.accel_key
        naccels_msgid = msgid.count(char)
        naccels_msgstr = msgstr.count(char)

        if naccels_msgid == 1:
            if naccels_msgstr == 1:
                return msgid.replace(char, ''), msgstr.replace(char, ''), None
            else:
                warning = 'Hotkey assignment inconsistency'
                return msgid, msgstr, warning

        return msgid, msgstr, None


class QuoteSubstitutionFilter:
    def __init__(self, quotechar):
        self.quotechar = quotechar
    
    def check(self, entry, msgid, msgstr):
        return msgid.replace("'", self.quotechar), msgstr, None


class POABC:
    def __init__(self, tests):
        self.entrycount = 0
        self.translatedcount = 0
        self.untranslatedcount = 0
        self.fuzzycount = 0
        self.tests = tuple(tests)

    def add_to_stats(self, entry):
        if not entry.msgid:
            return
        self.entrycount += 1
        if entry.istranslated:
            self.translatedcount += 1
        elif entry.isfuzzy:
            self.fuzzycount += 1
        else:
            self.untranslatedcount += 1

    def check_stringpair(self, entry, msgid, msgstr):
        if not msgid: # The header should have been filtered out already
            return msgid, msgstr, ['No msgid']
        if not msgstr: 
            # These have already been checked for if called
            # from check_entry
            return msgid, msgstr, ['Untranslated message']
        if entry.isfuzzy:
            return msgid, msgstr, ['Fuzzy message']

        warnings = []
        for test in self.tests:
            msgid, msgstr, warning = test.check(entry, msgid, msgstr)
            if warning:
                warnings.append(warning)
        return msgid, msgstr, warnings

    def check_entry(self, entry):
        warnings = []
        if len(entry.msgid) == 0:
            return warnings
        if not entry.istranslated:
            return ['Untranslated message']
        if entry.isfuzzy:
            return ['Fuzzy message']
        msgid, msgstr, warnings1 = self.check_stringpair(entry, entry.msgid,
                                                         entry.msgstr)
        warnings.extend(warnings1)
        
        if entry.hasplurals:
            msgid_plural = entry.msgid_plural
            for msgstr in entry.msgstrs[1:]:
                msgid, msgstr, morewarns = self.check_stringpair(entry,
                                                                 msgid_plural,
                                                                 msgstr)
            warnings.extend(morewarns)
        return warnings

    def check_entries(self, entries):
        for entry in entries:
            self.add_to_stats(entry)
            if is_translatorcredits(entry.msgid):
                continue
            warnings = self.check_entry(entry)
            if warnings:
                yield entry, warnings


def build_parser():
    usage = '%prog [OPTIONS] FILE'
    description = ('Parse a gettext translation file, writing suspected '
                   'errors to standard output.  Checks for a range of common '
                   'errors such as inconsistent case, punctuation and xml.')
    
    parser = OptionParser(usage=usage, description=description,
                          version=__version__)
    parser.add_option('-a', '--accel-char', default='_', metavar='CHAR',
                      help='hot key character.  Default: "%default"')
    parser.add_option('-c', '--context-char', default='|', metavar='CHAR',
                      help='context character.  Default: "%default"')
    parser.add_option('-q', '--filter-quote-characters', action='store_true',
                      help='warn about quote characters not following'
                      ' convention.')
    parser.add_option('-Q', '--quote-character', default='\\"', metavar='CHAR',
                      help='set the quote character.  Only relevant with -q.'
                      '  Default: %default')
    return parser


def header(linenumber):
    return ('--- Line %d ' % linenumber).ljust(32, '-')


def main():
    cmdparser = build_parser()
    opts, args = cmdparser.parse_args()
    nargs = len(args)
    if nargs == 0:
        cmdparser.print_help()
        raise SystemExit(0)
    elif nargs > 1:
        print >> sys.stderr, 'One file at a time, please.'
        raise SystemExit(1)
    
    allfiles = fileinput.input(args)
        
    parser = Parser()
    entries = parser.parse_asciilike(allfiles)

    tests = []
    tests.append(PartiallyTranslatedPluralTest())
    if opts.filter_quote_characters:
        quotechar = opts.quote_character
        tests.append(QuoteSubstitutionFilter(quotechar))
    if opts.context_char:
        tests.append(ContextCharTest(opts.context_char))
    if opts.accel_char:
        tests.append(AcceleratorTest(opts.accel_char))
    tests.append(LeadingCharTest())
    tests.append(TrailingCharTest())
    tests.append(XMLTest())
    tests.append(WordRepeatTest())

    poabc = POABC(tests)

    warningcount = 0 # total number of warnings
    entrywarncount = 0 # number of entries with at least one warning

    try:
        for entry, warnings in poabc.check_entries(entries):
            print header(entry.linenumber)
            warningcount += len(warnings)
            entrywarncount += 1
            for warning in warnings:
                print warning
            print entry.tostring().encode('utf8')
    except IOError, err:
        cmdparser.error(err)
        
    def fancyfmt(n):
        return '%d [%d%%]' % (n, round(100 * float(n) / poabc.entrycount))
        return (n, float(n) / poabc.entrycount)

    width = 50
    print ' Summary '.center(width, '=')
    print 'Number of messages: %d' % poabc.entrycount
    print 'Translated messages: %s' % fancyfmt(poabc.translatedcount)
    print 'Fuzzy messages: %s' % fancyfmt(poabc.fuzzycount)
    print 'Untranslated messages: %s' % fancyfmt(poabc.untranslatedcount)
    print 'Number of warnings: %d' % entrywarncount
    print '=' * width

if __name__ == '__main__':
    main()
