from __future__ import print_function, unicode_literals
import sys
from optparse import OptionParser

from pyg3t.gtparse import parse
from pyg3t.util import NullDevice, pyg3tmain, get_encoded_output, regex


description = """Check translations of command-line options in po-files."""


def build_parser():
    p = OptionParser(usage='%prog [OPTION] [FILE...]',
                     description=description)
    p.add_option('--quiet', action='store_true',
                 help='suppress normal output; print only count')
    p.add_option('--diagnostics', action='store_true',
                 help='print diagnostics')
    #p.add_option('--longlines', action='store_true',
    #             help='check for lines longer than 79 characters')
    return p

# e.g. HELLO
metavar = r'\w*'

# -p
single_short_noarg = r'-[a-zA-Z0-9\?]'

# -p  or  -p HELLO
single_short = r'(%s)( %s)?' % (single_short_noarg, metavar)

# -p, -q, -r
some_short = r'%s(, %s)*' % (single_short, single_short)

# --hello
single_long_noarg = r'--[a-z0-9][a-z0-9\-_]*'

# --hello  or  --hello=HELLO  or  --hello[=HELLO]
single_long = r'%s(=%s|\[=%s\])?' % (single_long_noarg, metavar, metavar)

# -p, -q, --hello, --hello-world=HELLO
any_short_some_long = r'(%s, )*(%s, )*%s' % (single_short, single_long,
                                             single_long)

# White space first (perhaps), then business, then either more whitespace
# (before a description) *or* end of line
full_short = r'^\s*%s(\s+|$)' % some_short
full_long = r'^\s*%s(\s+|$)' % any_short_some_long

# matches all of the above
option_pattern = r'(%s)|(%s)' % (full_long, full_short)

METAVAR = regex(metavar)
OPTION = regex(option_pattern)
leading_whitespace = regex(r'^\s+')
separators = regex(r'^\s+|, |\b \b|=|\s+$')


class Option:
    def __init__(self, match, group, lines):
        self.match = match
        self.group = group
        self.lines = lines

        self.firstindent = len(self.group)
        self.groups = [g for g in match.groups()[1:]
                       if group is not None]

        if len(lines) > 1:
            wmatch = leading_whitespace.match(lines[1])
            if wmatch:
                wspace = len(wmatch.group())
            else:
                wspace = 0
            self.nextindent = wspace
        else:
            self.nextindent = None


class BadOption(ValueError):
    pass


class OptionChecker:
    def __init__(self, longlines=True, debugfile=None):
        self.longlines = longlines
        if debugfile is None:
            debugfile = NullDevice()
        self.debug = debugfile

    def diagnostics(self, msgidline, text):
        #n = msg.meta['lineno']
        strlen = 25
        msgidline = msgidline.lstrip()
        if len(msgidline) > strlen:
            msgidline = '%s...' % msgidline[:strlen - 2]
        print('"%26s": %s' % (msgidline, text), file=self.debug)

    def get_options(self, string):
        # For each option we make a *group*.  The group consists of
        # all lines pertaining to that option (definition and description).
        #
        # One msgid may specify several options, so there'll be a list
        # of groups.
        lines = []
        matches = []
        groups = []
        options = []

        # Upper limit of description indentation level
        indent_guess = 75

        for line in string.split('\\n'):
            if not line:
                # Throw out empty lines at the end as well as
                # descriptions that are not indented
                continue
            match = OPTION.match(line)
            #print line
            leadingspace_match = leading_whitespace.match(line)
            if leadingspace_match:
                leadingspace = len(leadingspace_match.group())
            else:
                leadingspace = 0

            # use heuristic to avoid "false" options when a line in the
            # description starts with dash
            if match and leadingspace < indent_guess // 2:
                self.diagnostics(line.lstrip(), 'Option found')
                lines = []
                group = match.group()
                #print group
                matches.append(match)
                groups.append(group)
                options.append(lines)
                if len(group) + 1 < len(line): # i.e. if there IS a description
                    indent_guess = min(indent_guess, len(group))
            else:
                self.diagnostics(line.lstrip(), 'Not an option')
            lines.append(line)

        options1 = []
        for match, group, lines in zip(matches, groups, options):
            option = Option(match, group, lines)
            options1.append(option)
        return options1

    def checkoptions(self, msg):
        #msg = msg.decode()
        if not msg.istranslated:
            return

        msgid_options = self.get_options(msg.msgid)
        msgstr_options = self.get_options(msg.msgstr)

        if len(msgid_options) == 0:
            return

        if len(msgid_options) != len(msgstr_options):
            raise BadOption('Unequal number of options: %d vs %d'
                            % (len(msgid_options), len(msgstr_options)))

        for opt1, opt2 in zip(msgid_options, msgstr_options):

            tokens1 = separators.split(opt1.group)
            tokens2 = separators.split(opt2.group)

            if len(tokens1) != len(tokens2):
                raise BadOption('Different number of options/vars or bad'
                                ' separators')

            for g1, g2 in zip(tokens1, tokens2):
                if g1 == g2:
                    continue
                if g1.isupper() and g2.isupper():
                    if opt1.group.count(g1) != opt2.group.count(g2):
                        raise BadOption('Metavar %s not matched in translation'
                                        % g1)
                    continue
                if g1.startswith('--') and g1 != g2:
                    raise BadOption('Long option %s not found in translation'
                                    % g1)
                elif g1.startswith('-') and len(g1) == 2 and g1 != g2:
                    raise BadOption('Short option %s not found in translation'
                                    % g1)

            if opt1.firstindent != opt2.firstindent:
                # It's OK if there wasn't enough space
                # Only complain if there's more than 2 chars of space
                # Also, perhaps it is the English one which is squeezed
                msgstr_bad = (len(opt2.group.rstrip()) + 2 < opt2.firstindent)
                if msgstr_bad:
                    raise BadOption('Bad indentation of option line')

            if self.longlines:
                msgid_fits = all(len(line) < 80 for line in opt1.lines)
                msgstr_fits = all(len(line) < 80 for line in opt2.lines)
                if msgid_fits and not msgstr_fits:
                    raise BadOption('Lines longer than 80 characters')
            # XXX check subsequent indent
        print(('OK : Line %d. ' % msg.meta['lineno']).ljust(78, '-'),
              file=self.debug)


@pyg3tmain(build_parser)
def main(parser):
    opts, args = parser.parse_args()

    errcount = 0

    debug = None
    out = get_encoded_output('utf8')
    if opts.diagnostics:
        debug = out

    checker = OptionChecker(debugfile=debug)

    for arg in args:
        fd = open(arg, 'rb')
        cat = parse(fd)
        for msg in cat:
            # we ignore plurals.  Who would write command-like
            # arguments with multiple plural versions?
            try:
                checker.checkoptions(msg)
            except BadOption as e:
                errcount += 1
                if not opts.quiet:
                    string = 'Line %d: %s' % (msg.meta['lineno'], e.args[0])
                    if opts.diagnostics:
                        print(('ERR: %s '
                               % string).ljust(78, '-'), file=checker.debug)
                    else:
                        print(string, file=out)
                        print('-' * len(string), file=out)
                        print(msg.tostring(), file=out)
    if errcount == 1:
        print('Found 1 error.', file=out)
    else:
        print('Found %d errors.' % errcount, file=out)

    exitcode = int(errcount > 0)
    sys.exit(exitcode)
