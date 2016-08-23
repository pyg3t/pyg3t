#!/usr/bin/env python

"""Perform grep-like operations on message catalogs."""

from __future__ import print_function, unicode_literals
import os
import re
from optparse import OptionParser, OptionGroup

from pyg3t import __version__
from pyg3t.gtparse import iparse
from pyg3t.util import ansi, pyg3tmain, get_encoded_output,\
    get_bytes_input, PoError, regex
#from pyg3t.annotate import annotate, annotate_ref


illegal_accel_chars = '*+?{}()|[]'


def build_parser():
    ulines = ['%prog [OPTION...] PATTERN [FILE...]',
             '%prog --COMPONENT PATTERN [OPTION...] [FILE...]']
    usage = ('\n' + ' ' * len('Usage: ')).join(ulines)

    desc = ('Search FILEs and print messages that match PATTERN, '
            'ignoring syntactical artifacts of catalogs.  '
            'If no FILE is given, or FILE is -, read from stdin.  '
            'In 1st form, match any part of the message.  '
            'In 2nd form, match --COMPONENTs as listed below.  '
            'If multiple --COMPONENT PATTERNs are given, messages must '
            'match all of them.')

    parser = OptionParser(usage=usage, description=desc,
                          version=__version__)

    match = OptionGroup(parser, 'Matching options')
    components = OptionGroup(parser, 'Message COMPONENTs')
    output = OptionGroup(parser, 'Output options')

    components.add_option('--comment', metavar='PATTERN',
                          help='match in comments')
    components.add_option('-i', '--msgid', metavar='PATTERN',
                          help='match in msgid and msgid_plural')
    components.add_option('-s', '--msgstr', metavar='PATTERN',
                          help='match in msgstrs')
    components.add_option('--icomment', metavar='PATTERN',
                          help='inverse-match in comments')
    components.add_option('-I', '--imsgid', metavar='PATTERN',
                          help='inverse-match in msgid and msgid_plural')
    components.add_option('-S', '--imsgstr', metavar='PATTERN',
                          help='inverse-match in msgstrs')

    match.add_option('--case', action='store_true',
                     help='use case sensitive matching')
    match.add_option('--accel', metavar='CHAR',
                     help='character which is ignored when matching.  '
                     'Useful for accelerator keys, typically _ or &.')

    output.add_option('-C', '--count', action='store_true',
                      help='print only a count of matching messages')
    output.add_option('-c', '--color', action='store_true',
                      help='highlight matches with colors')
    output.add_option('-n', '--line-numbers', action='store_true',
                      help='print line numbers for each message')
    output.add_option('-G', '--gettext', action='store_true',
                      help='write output as valid gettext catalog.  '
                      'include header and print annotations as comments.')
    output.add_option('--annotate', action='store_true',
                      help='write annotations for back-merging')

    parser.add_option_group(components)
    parser.add_option_group(match)
    parser.add_option_group(output)
    return parser


grep_components = ['comment', 'msgid', 'msgstr']


class SearchOp:
    def __init__(self, attribute, pattern, replace, multiple=False):
        self.attribute = attribute
        self.pattern = pattern
        self.replace = replace
        self.multiple = multiple

    def _process_string(self, string):
        return self.pattern.subn(self.replace, string)

    def __call__(self, msg):
        nhits = 0
        attribute = getattr(msg, self.attribute)
        if attribute is None:
            return False
        if self.multiple:
            for i, string in enumerate(attribute):
                attribute[i], n = self._process_string(string)
                nhits += n
        else:
            newstring, n = self._process_string(attribute)
            setattr(msg, self.attribute, newstring)
            nhits += n
        return nhits > 0


def logical_and(ops):
    def check(msg):
        return all([op(msg) for op in ops])
    return check


def logical_or(ops):
    def check(msg):
        return any([op(msg) for op in ops])
    return check


def logical_not(op):
    def check(msg):
        return not op(msg)
    return check


@pyg3tmain(build_parser)
def main(parser):
    opts, fnames = parser.parse_args()
    out = get_encoded_output('utf-8')

    if opts.accel:
        if len(opts.accel) > 1:
            parser.error('Accelerator key should be one character, '
                         'but is "%s"' % opts.accel)
        if opts.accel in illegal_accel_chars:
            parser.error('Illegal accelerator key: %s.  Cannot be any of '
                         '%s' % (opts.accel, illegal_accel_chars))

    flags = 0
    if not opts.case:
        flags |= re.IGNORECASE

    def re_compile(pattern):
        try:
            return regex(pattern, flags=flags)
        except re.error as err:
            msg = 'bad pattern %s: %s' % (pattern, str(err))
            raise PoError('bad-gtgrep-pattern', msg)

    # Collect all the patterns for --msgid, --imsgid, etc.:
    patterns = {}
    optiondict = vars(opts)
    for component in grep_components:
        for c in [component, 'i' + component]:
            if optiondict[c] is not None:
                patterns[c] = optiondict[c]

    match_strategy = logical_and

    # If there were none, take PATTERN from arguments, and match "any":
    if len(patterns) == 0:
        try:
            pattern = fnames.pop(0)
        except IndexError:
            parser.error('No PATTERNs given')
        else:
            match_strategy = logical_or
            patterns = {'msgctxt': pattern}  # Cannot be enabled externally
            for key in grep_components:
                patterns[key] = pattern

    if opts.color:
        replace = lambda match: ansi.light_blue(match.group())
    else:
        replace = lambda match: match.group()

    def get_accel_pattern(pattern):
        if not opts.accel:
            return pattern

        # Yuck!!  We convert pattern into p_?a_?t_?t_?e_?r_?n.  Oh the pain
        for char in illegal_accel_chars:
            if char in pattern:
                err = ('Sorry, patterns containing any of %s '
                       'are not supported with --accel' % illegal_accel_chars)
                parser.error(err)
        return (opts.accel + '?').join(list(pattern))

    ops = []

    for key, pattern in patterns.items():
        if key in ['comment', 'icomment']:
            regex_obj = re_compile(pattern)
            accel_regex_obj = re_compile(get_accel_pattern(pattern))
            op1 = SearchOp('comments', regex_obj, replace, multiple=True)
            op2 = SearchOp('previous_msgctxt', regex_obj, replace)
            op3 = SearchOp('previous_msgid', accel_regex_obj, replace)
            op = logical_or([op1, op2, op3])
            if key == 'icomment':
                op = logical_not(op)
            ops.append(op)

        elif key == 'msgctxt':
            ops.append(SearchOp('msgctxt', re_compile(pattern), replace))

        elif key in ['msgid', 'imsgid']:
            regex_obj = re_compile(get_accel_pattern(pattern))
            op1 = SearchOp('msgid', regex_obj, replace)
            op2 = SearchOp('msgid_plural', regex_obj, replace)
            op = logical_or([op1, op2])
            if key == 'imsgid':
                op = logical_not(op)
            ops.append(op)

        elif key in ['msgstr', 'imsgstr']:
            regex_obj = re_compile(get_accel_pattern(pattern))
            op = SearchOp('msgstrs', regex_obj, replace, multiple=True)
            if key == 'imsgstr':
                op = logical_not(op)
            ops.append(op)

        else:
            assert False, 'Internal error: %s' % key

    # final search operation is either logical AND or logical OR of everything
    op = match_strategy(ops)

    if not fnames:
        fnames = ['-']

    if opts.annotate:
        from pyg3t.annotate import ref_template
        annotation = ref_template  # XXX
    elif len(fnames) > 1:
        annotation = '%(fname)s:%(lineno)d\n'
    else:
        annotation = 'Line %(lineno)d\n'

    if opts.gettext:
        annotation = '# pyg3t: %s' % annotation
    if opts.color:
        annotation = ansi.red(annotation)

    def print_message(msg):
        if opts.line_numbers or opts.annotate:
            tmpfname = os.path.abspath(fname) if opts.annotate else fname
            print(annotation % dict(fname=tmpfname, lineno=msg.meta['lineno']),
                  file=out)
        print(msg.tostring(), file=out)

    if opts.gettext and opts.annotate:
        parser.error('Conflicting options: --gettext and --annotate')

    for fname in fnames:
        fd = get_bytes_input(fname)
        cat = iparse(fd)

        hits = 0
        if opts.gettext or opts.annotate:
            # Make sure to print header whether it matches or not
            header = next(cat)
            if op(header):  # May add coloring
                hits += 1
            if not opts.count:
                print_message(header)

        for msg in cat:
            if op(msg):
                hits += 1
                if not opts.count:
                    print_message(msg)

        if opts.count:
            fmt = '%(hits)d'
            if opts.color:
                fmt = ansi.purple(fmt)
            if len(fnames) > 1:
                filefmt = '%(fname)s'
                if opts.color:
                    filefmt = ansi.red(filefmt)
                fmt = '%s:%s' % (filefmt, fmt)

            print(fmt % dict(fname=fname, hits=hits), file=out)
