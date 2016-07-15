#!/usr/bin/env python

from __future__ import print_function, unicode_literals
import sys
import fileinput
import itertools
from optparse import OptionParser

from pyg3t.gtparse import parse, get_encoded_stdout
from pyg3t.gtxml import GTXMLChecker
from pyg3t.util import pyg3tmain
from pyg3t import __version__
import xml.sax


def is_translatorcredits(msgid):
    return msgid in ['translator-credits', 'translator_credits']


class PartiallyTranslatedPluralTest:
    def check(self, msg, msgid, msgstr):
        warn = None
        if msgstr == '':
            warn = 'Some plurals not translated'
        return msgid, msgstr, warn


class XMLTest:
    def __init__(self):
        self.checker = GTXMLChecker()

    def check(self, msg, msgid, msgstr):
        warn = None
        try:
            self.checker.check_msg(msg)
        except xml.sax.SAXParseException as err:
            warn = 'Invalid xml: ' + str(err)
        return msgid, msgstr, warn


class WordRepeatTest:
    def check(self, msg, msgid, msgstr):
        words = msgstr.split()
        for word1, word2 in zip(words[:-1], words[1:]):
            if word1.isalpha() and word1 == word2:
                warn = 'Repeated word: "%s"' % word1
                return msgid, msgstr, warn
        return msgid, msgstr, None


class ContextCharTest:
    def __init__(self, context_char):
        self.context_char = context_char

    def check(self, msg, msgid, msgstr):
        index1 = msgid.find(self.context_char)
        warn = None
        if index1 == -1:
            return msgid, msgstr, warn

        msgid = msgid[index1 + len(self.context_char):]
        index2 = msgstr.find(self.context_char)
        if index2 != -1:
            warn = 'Context character "%s" found in msgstr' % \
                self.context_char
            msgstr = msgstr[index2 + len(self.context_char):]
        return msgid, msgstr, warn


def sametype(msgid, msgstr):
    for n, (ichar, schar) in enumerate(zip(msgid, msgstr)):
        if ichar.isalpha() and schar.isalpha():
            return True, n
        if ichar != schar:
            return False, n
    return True, n


class LeadingCharTest:
    def check(self, msg, msgid, msgstr):
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
    def check(self, msg, msgid, msgstr):
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

    def check(self, msg, msgid, msgstr):
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

    def check(self, msg, msgid, msgstr):
        return msgid.replace("'", self.quotechar), msgstr, None


class POABC:
    def __init__(self, tests):
        self.msgcount = 0
        self.translatedcount = 0
        self.untranslatedcount = 0
        self.fuzzycount = 0
        self.tests = tuple(tests)

    def add_to_stats(self, msg):
        if not msg.msgid:
            return
        self.msgcount += 1
        if msg.istranslated:
            self.translatedcount += 1
        elif msg.isfuzzy:
            self.fuzzycount += 1
        else:
            self.untranslatedcount += 1

    def check_stringpair(self, msg, msgid, msgstr):
        if not msgid: # The header should have been filtered out already
            return msgid, msgstr, ['No msgid']
        if not msgstr:
            # These have already been checked for if called
            # from check_msg
            return msgid, msgstr, ['Untranslated message']
        if msg.isfuzzy:
            return msgid, msgstr, ['Fuzzy message']

        warnings = []
        for test in self.tests:
            msgid, msgstr, warning = test.check(msg, msgid, msgstr)
            if warning:
                warnings.append(warning)
        return msgid, msgstr, warnings

    def check_msg(self, msg):
        warnings = []
        if len(msg.msgid) == 0:
            return warnings
        if not msg.istranslated:
            return ['Untranslated message']
        if msg.isfuzzy:
            return ['Fuzzy message']
        #msg = msg.decode()
        msgid, msgstr, warnings1 = self.check_stringpair(msg, msg.msgid,
                                                         msg.msgstr)
        warnings.extend(warnings1)

        if msg.hasplurals:
            msgid_plural = msg.msgid_plural
            for msgstr in msg.msgstrs[1:]:
                msgid, msgstr, morewarns = self.check_stringpair(msg,
                                                                 msgid_plural,
                                                                 msgstr)
            warnings.extend(morewarns)
        return warnings

    def check_msgs(self, msgs):
        for msg in msgs:
            self.add_to_stats(msg)
            if is_translatorcredits(msg.msgid):
                continue
            warnings = self.check_msg(msg)
            if warnings:
                yield msg, warnings


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


@pyg3tmain
def main():
    cmdparser = build_parser()
    opts, args = cmdparser.parse_args()
    nargs = len(args)
    if nargs == 0:
        cmdparser.print_help()
        raise SystemExit(0)
    elif nargs > 1:
        print('One file at a time, please.', file=sys.stderr)
        raise SystemExit(1)

    fname = args[0]
    if fname == '-':
        fd = sys.stdin  # XXX how to wrap this?
    else:
        fd = open(fname, 'rb')

    # XXX does this work with multiple files actually?
    cat = parse(fd)

    # We will not respect the original coding of the file
    out = get_encoded_stdout('utf-8')

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
    msgwarncount = 0 # number of msgs with at least one warning

    for msg, warnings in poabc.check_msgs(cat):
        print(header(msg.meta['lineno']), file=out)
        warningcount += len(warnings)
        msgwarncount += 1
        for warning in warnings:
            print(warning, file=out)
        print(msg.rawstring(), file=out)

    def fancyfmt(n):
        return '%d [%d%%]' % (n, round(100 * float(n) / poabc.msgcount))

    width = 50
    print(' Summary '.center(width, '='), file=out)
    print('Number of messages: %d' % poabc.msgcount, file=out)
    print('Translated messages: %s' % fancyfmt(poabc.translatedcount),
          file=out)
    print('Fuzzy messages: %s' % fancyfmt(poabc.fuzzycount), file=out)
    print('Untranslated messages: %s' % fancyfmt(poabc.untranslatedcount),
          file=out)
    print('Number of warnings: %d' % msgwarncount, file=out)
    print('=' * width, file=out)

if __name__ == '__main__':
    main()
