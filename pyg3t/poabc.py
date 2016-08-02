#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
from optparse import OptionParser, OptionGroup
import re

from pyg3t.gtparse import iparse
from pyg3t.gtxml import GTXMLChecker
from pyg3t.util import (pyg3tmain, get_bytes_input, get_encoded_output, ansi,
                        noansi)
from pyg3t import __version__
import xml.sax


headerwidth = 72


class Trouble:
    def __init__(self, errmsg, string=None, start=None, end=None):
        self.errmsg = errmsg
        self.string = string
        self.start = start
        self.end = end

    def tostring(self):
        return self.errmsg


def is_translatorcredits(msgid):
    return msgid in ['translator-credits', 'translator_credits']


class PartiallyTranslatedPluralTest:
    def check(self, msg, msgid, msgstr):
        warn = []
        if msg.istranslated and msgstr == '':
            warn = [Trouble('Some plurals not translated')]
        return msgid, msgstr, warn


class XMLTest:
    def __init__(self):
        self.checker = GTXMLChecker()

    def check(self, msg, msgid, msgstr):
        warn = []
        try:
            self.checker.check_msg(msg)
        except xml.sax.SAXParseException as err:
            col = err.getColumnNumber() - len('<xml>')  # XXXXXX hack
            warn = [Trouble('Invalid xml: ' + str(err),
                            msgstr, col - 3, col + 3)]
        return msgid, msgstr, warn


class WordRepeatTest:
    def __init__(self):
        # This is mostly a problem in the middle of sentences, and if
        # something is in the beginning or end, it is usually a false positive.
        # Thus, we really want to match ' word word '.
        # One can argue that \w is too general (numbers), but it is simple
        # and works transparently for all languages (unicode)
        pat = (r'(?<=\s)'  # Match only when preceded by space
               r'(?P<repetition>'
               r'(?P<word>\w+)'  # Any word
               r' '  # Whitespace.  Only one, else tables make lots of noise
               r'\b(?P=word)\b'  # The same word
               r')(?=\s+)')
        self.pattern = re.compile(pat, re.UNICODE)

    def check(self, msg, msgid, msgstr):
        warns = []
        for match in self.pattern.finditer(msgstr):
            assert hasattr(match, 'group')  # Match objects
            group = match.group('repetition')
            warn = 'Repeated word: "%s"' % group
            warns.append(Trouble(warn, msgstr, match.start(), match.end()))
        return msgid, msgstr, warns


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
    def __init__(self):
        self.ending = re.compile(r'(?P<ending>(?P<word>\S+)(?P<space>\s*))?$',
                                 re.UNICODE)

    def extract_ending(self, string):
        """Return (last_word, trailing_space)."""
        match = self.ending.search(string)
        if match is None:
            assert string.isspace()
            return None, None, None
        return match.group('ending'), match.group('word'), match.group('space')

    def check(self, msg, msgid, msgstr):
        msgid_end, msgid_word, msgid_space = self.extract_ending(msgid)
        msgstr_end, msgstr_word, msgstr_space = self.extract_ending(msgstr)
        if msgid_end is None or msgstr_end is None:
            return msgid, msgstr, []  # Not our job

        warn = []

        # Ellipsize endings for errmsgs if they are very long:
        w1 = msgid_end
        if len(w1) > 20:
            w1 = '...%s' % w1[-16:]
        w2 = msgstr_end
        if len(w2) > 20:
            w2 = '...%s' % w2[-16:]
        endings = '"%s" vs "%s"' % (w1, w2)

        if msgstr_space and not msgid_space:
            # Translator added whitespace.  This  is probably an error.
            # (Sometimes the translator removes whitespace on purpose.)
            warn.append(Trouble('Trailing whitespace', endings))

        # Typical string like "File: ", where something is meant to come after.
        # In this case the translation should likely not remove the space.
        if msgid_word.endswith(':') and msgid_space and not msgstr_space:
            warn.append(Trouble('Translation removes whitespace after colon',
                                endings))

        ellipsis = ('…', '...')
        if msgid_word.endswith(ellipsis) != msgstr_word.endswith(ellipsis):
            warn.append(Trouble('Inconsistent use of ellipsis', endings))

        if re.search(r'\w\.$', msgid_word) and not msgstr_word.endswith('.'):
            warn.append(Trouble('Translation removes period', endings))

        if re.search(r'\w\?$', msgid_word) and not msgstr_word.endswith('?'):
            warn.append(Trouble('Translation removes question mark', endings))

        # It is considered okay to remove a '!' without adding anything
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
        assert msg.msgid is not None

        warnings = []
        for test in self.tests:
            msgid, msgstr, warn = test.check(msg, msgid, msgstr)
            warnings.extend(warn)
        return msgid, msgstr, warnings

    def check_msg(self, msg):
        if len(msg.msgid) == 0:
            return []

        warnings = []

        msgid, msgstr, warnings1 = self.check_stringpair(msg, msg.msgid,
                                                         msg.msgstr)
        msg.msgid = msgid
        msg.msgstrs[0] = msgstr
        warnings.extend(warnings1)

        if msg.isplural:
            msgid_plural = msg.msgid_plural
            for i, msgstr in enumerate(msg.msgstrs[1:]):
                msgid, msgstr, morewarns = self.check_stringpair(msg,
                                                                 msgid_plural,
                                                                 msgstr)
                warnings.extend(morewarns)
                msg.msgstrs[1 + i] = msgstr
            msg.msgid_plural = msgid_plural
        return warnings

    def check_msgs(self, msgs):
        for msg in msgs:
            self.add_to_stats(msg)
            if not msg.istranslated:
                continue
            if is_translatorcredits(msg.msgid):
                continue
            warnings = self.check_msg(msg)
            if warnings:
                yield msg, warnings


def build_parser():
    usage = '%prog [OPTION...] FILE...'
    description = ('Find suspected errors in gettext catalog.  '
                   '%prog checks for a range of common errors such as '
                   'inconsistent punctuation, repeated words, or invalid '
                   'xml.  See checks below.  All checks enabled by default; '
                   'if any checks are explicitly given, only the given checks '
                   'will be enabled.')

    parser = OptionParser(usage=usage, description=description,
                          version=__version__)
    #parser.add_option('-a', '--accel-char', default='_', metavar='CHAR',
    #                  help='hot key character.  Default: "%default"')
    #parser.add_option('-q', '--filter-quote-characters', action='store_true',
    #                  help='warn about quote characters not following'
    #                  ' convention.')
    #parser.add_option('-Q', '--quote-character', default='\\"', metavar='CHAR',
    #                  help='set the quote character.  Only relevant with -q.'
    #                  '  Default: %default')
    parser.add_option('-c', '--color', action='store_true',
                      help='use colors to highlight output')
    parser.add_option('--quiet', action='store_true',
                      help='do not print full message')


    checkopts = OptionGroup(parser, 'Checks')
    for key in sorted(poabc_checks.keys()):
        checkopts.add_option('--%s' % key, action='store_true',
                             help=poabc_checks[key])
    parser.add_option_group(checkopts)
    return parser


poabc_checks = {'xml': 'check xml',
                'trailing': 'check trailing characters',
                'plurals': ('find untranslated plurals of otherwise '
                            'translated messages'),
                'repeat': 'find repeated words'}


def format_context(trouble, use_color):
    txt = trouble.string
    s1 = trouble.start
    s2 = trouble.end

    draw_arrow = True

    if s1 is None:
        assert s2 is None
        draw_arrow = False
        s1 = 0
        s2 = 0
    assert s2 is not None

    left_ellipsis = ''
    part1 = txt[:s1]
    part2 = txt[s1:s2]
    part3 = txt[s2:]
    right_ellipsis = ''


    ellipsis = '...'

    def left_ellipsize(string, maxlen):
        assert maxlen > 0
        out = re.split(r'\s', string[-maxlen:], 1)[-1]
        assert len(out) <= maxlen
        return out

    def right_ellipsize(string, maxlen):
        return left_ellipsize(string[::-1], maxlen)[::-1]

    startmarker = '>> '
    maxlen = 78 - len(startmarker)

    # First and last elements may be replaced by ellipsis

    if len(part1) + len(part2) + len(part3) > maxlen:
        if len(part2) > 60:
            # Forget it, just return the damn thing
            pass
        else:
            partmaxlen = (maxlen - len(part2)) // 2 - len(ellipsis)
            assert partmaxlen > 0
            if len(part1) > partmaxlen:
                part1 = left_ellipsize(part1, partmaxlen)
                assert len(part1) <= partmaxlen
                left_ellipsis = ellipsis
            if len(part3) > partmaxlen:
                part3 = right_ellipsize(part3, partmaxlen)
                assert len(part3) <= partmaxlen
                right_ellipsis = ellipsis

    if use_color:
        part1 = ansi.purple(part1) if part1 else ''
        part2 = ansi.light_red(part2) if part2 else ''
        part3 = ansi.purple(part3) if part3 else ''

    tokens = [startmarker, left_ellipsis, part1]
    left_len = sum(len(noansi(x)) for x in tokens)
    tokens.extend([part2, part3, right_ellipsis])

    if draw_arrow:
        tokens.append('\n')
        tokens.append(' ' * (left_len + len(noansi(part2)) // 2))
        arrow = '^'
        if use_color:
            arrow = ansi.light_green(arrow)
        tokens.append(arrow)
    return ''.join(tokens)


@pyg3tmain(build_parser)
def main(cmdparser):
    opts, args = cmdparser.parse_args()
    nargs = len(args)
    if nargs == 0:
        cmdparser.print_help()
        cmdparser.exit()

    headerfmt = 'Line %(lineno)d'
    if nargs > 1:
        headerfmt = '%(fname)s line %(lineno)d'

    def get_header(pad=True, **kwargs):
        string = headerfmt % kwargs
        if pad:
            string = ('--- %s ' % string).ljust(headerwidth, '-')
        if opts.color:
            string = ansi.cyan(string)
        return string

    # We will not respect the original coding of the file
    out = get_encoded_output('utf-8')

    tests = []

    optiondict = vars(opts)
    for test in sorted(poabc_checks):
        if optiondict[test]:
            tests.append(test)

    if not tests:  # No tests given.  Enable all of them
        tests = list(sorted(poabc_checks))

    testclasses = dict(plurals=PartiallyTranslatedPluralTest,
                       xml=XMLTest,
                       trailing=TrailingCharTest,
                       repeat=WordRepeatTest)

    # Convert test names to objects
    tests = [testclasses[name]() for name in tests]

    #if opts.filter_quote_characters:
    #    quotechar = opts.quote_character
    #    tests.append(QuoteSubstitutionFilter(quotechar))
    #if opts.accel_char:
    #    tests.append(AcceleratorTest(opts.accel_char))
    #tests.append(LeadingCharTest())

    poabc = POABC(tests)

    warningcount = 0 # total number of warnings
    msgwarncount = 0 # number of msgs with at least one warning

    for arg in args:
        fd = get_bytes_input(arg)
        fname = fd.name

        fileheader_unfinished = False

        if nargs > 1:
            fileheader = fname
            if opts.color:
                fileheader = ansi.light_blue(fname)
            print(fileheader, end='', file=out)
            fileheader_unfinished = True

        cat = iparse(fd, obsolete=False, trailing=False)

        thisfilewarnings = 0

        for msg, warnings in poabc.check_msgs(cat):
            if fileheader_unfinished:
                warn = ' [Warning]'
                if opts.color:
                    warn = ansi.light_red(warn)
                print(warn, file=out, end='\n\n')
                fileheader_unfinished = False

            header = get_header(lineno=msg.meta['lineno'], fname=fname,
                                pad=not bool(opts.quiet))
            print(header, file=out)
            warningcount += len(warnings)
            msgwarncount += 1
            thisfilewarnings += 1
            for warning in warnings:
                wstring = warning.tostring()
                if opts.color:
                    wstring = ansi.red(wstring)
                print(wstring, file=out)
                if warning.string:
                    print(format_context(warning, use_color=opts.color),
                          file=out)
            if opts.quiet:
                print(file=out)
            else:
                print(''.join(msg.meta['rawlines']), file=out)

        if thisfilewarnings == 0:
            ok = ' [OK!]'
            if opts.color:
                ok = ansi.light_green(ok)
            print(ok, file=out)

    def fancyfmt(n):
        return '%d [%d%%]' % (n, round(100 * float(n) / poabc.msgcount))

    print(' Summary '.center(headerwidth, '='), file=out)
    if nargs > 1:
        print('Number of files: %d' % nargs, file=out)
    print('Number of messages: %d' % poabc.msgcount, file=out)
    print('Translated messages: %s' % fancyfmt(poabc.translatedcount),
          file=out)
    print('Fuzzy messages: %s' % fancyfmt(poabc.fuzzycount), file=out)
    print('Untranslated messages: %s' % fancyfmt(poabc.untranslatedcount),
          file=out)
    print('Number of warnings: %d' % msgwarncount, file=out)
    print('=' * headerwidth, file=out)
