#!/usr/bin/env python
"""
gtparse -- A gettext parsing module in Python
Copyright (C) 2007-2010  Ask Hjorth Larsen <asklarsen@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from __future__ import print_function, unicode_literals
from codecs import iterdecode
import itertools
import sys
import time

from pyg3t.util import PoError, regex
from pyg3t.charsets import get_normalized_encoding_name
from pyg3t.message import Catalog, Message, ObsoleteMessage, Comments

# It is recommended that the license should be the first comment in each source
# code file, but it doesn't make a good module level doc string, so supply one
# manually

__doc__ = """
The gtparse module contains the basic functionality to parse
:term:`gettext catalog` s (.po files). The most important items are:

 * The :py:func:`.parse` function, which parses an entire gettext catalog from
   a file. **This function is the main entry point for the module**.
 * The :py:func:`.iparse` function similarly parses a file but returns an
   iterator over the messages.  First message is guaranteed to be the header.
 * The basic types for a single :py:class:`.Message` and for a single
   :py:class:`.ObsoleteMessage` .
 * The basic type for a :py:class:`.Catalog` that represents an entire gettext
   catalog worth of messages

.. data:: patterns

    Dictionary of compiled regular expression objects used to parse active
    messages in the .po files.  Each regex parses one line.

.. data:: obsolete_patterns

    Dictionary of compiled regular expression objects, corresponding to
    :py:data:`.patterns` with ``'#~'`` prefixed.  Used to parse
    obsolete messages in the .po files
""".lstrip()


# Content-Type should generally be text/plain
# TODO Issue warning otherwise.
#charset_extraction_pattern = regex(r'^Content-Type:\s*[^;]*;'
#                                   r'\s*charset=(?P<charset>[^\\]*)')
charset_extraction_pattern = regex(r'[^;]*;\s*charset=(?P<charset>[^\\]*)')


def parse_header_data(msgstr):
    """Parse the data in the .po file header.

    Header data looks like this:

    .. code-block:: python

       Project-Id-Version: nautilus
       Report-Msgid-Bugs-To: http://bugzilla.gnome.org/enter_bug.cgi?
       product=nautilus&keywords=I18N+L10N&component=Internationalization (i18n)
       POT-Creation-Date: 2015-08-26 23:10+0000
       PO-Revision-Date: 2015-03-14 03:30+0100
       Last-Translator: Ask Hjorth Larsen <asklarsen@gmail.com>
       Language-Team: Danish <dansk@dansk-gruppen.dk>
       Language: da
       MIME-Version: 1.0
       Content-Type: text/plain; charset=UTF-8
       Content-Transfer-Encoding: 8bit
       Plural-Forms: nplurals=2; plural=(n != 1);

    where each line is a key, value pair of header data separated by the
    first colon.

    Args:
        msgstr (string): The message that contains the header

    Returns:
        dict: Key, value pairs of header info. All keys and values are strings.

    Raises:
        PoError: On missing 'Content-Type' field, on 'Content-Type field from
            which the charset cannot be extracted or on a unknown charset
    """
    headers = {}
    for line in msgstr.split(r'\n'):
        if not line or line.isspace():
            continue  # wtf
        tokens = line.split(':', 1)
        if len(tokens) != 2:
            continue # XXXXXX write warning
        key, value = tokens  # Chance of shenanigans?
        # This should probably not be the case but isn't ugly
        # enough to complain extremely loudly about by default
        headers[key.strip()] = value.strip()

    if 'Content-Type' not in headers:
        raise PoError('no-content-type',
                      'No Content-Type in headers, or malformed headers:\n\n%s'
                      % msgstr.replace('\\n', '\\n\n'))
    match = charset_extraction_pattern.match(headers['Content-Type'])
    if not match:
        raise PoError('no-charset', 'Cannot extract charset from header "%s"' %
                      headers['Content-Type'])

    # Normalize charset
    charset_string = match.group('charset')
    try:
        charset = get_normalized_encoding_name(charset_string)
    except LookupError as err:
        raise PoError('bad-charset', 'Charset not recognized: %s' % str(err))

    # Extract more info?
    return charset, headers


def generate_po_header():
    # Todo: accept arguments
    timestr = time.strftime('%Y-%m-%d %H:%M%z')
    fields = ['Project-Id-Version: poabc-output',
              'POT-Creation-Date: %s' % timestr,
              'PO-Revision-Date: %s' % timestr,
              'Last-Translator: TRANSLATOR',
              'Language-Team: TEAM',
              'Language: LANGUAGE',
              'MIME-Version: 1.0',
              'Content-Type: text/plain; charset=utf-8',
              'Content-Transfer-Encoding: 8bit']
    header = r'\n'.join(fields)
    _, headers = parse_header_data(header)
    msg = Message(msgid='',
                  msgstr=header,
                  meta={'headers': headers})
    return msg


obsolete_pattern = regex(r'\s*#~')
obsolete_extraction_pattern = regex(r'\s*#~\s*(?P<line>.*)')


def getfilename(fd):
    try:
        name = fd.name
    except AttributeError:
        name = '<unknown>'
    return name


class ParseError(PoError):
    def __init__(self, header, regex, line, prev_lines):
        self.header = header
        self.regex = regex
        self.line = line
        self.prev_lines = prev_lines
        super(ParseError, self).__init__('parse-error')

    def get_errmsg(self):
        lines = ['Bad syntax while parsing',
                 'Filename: %s' % self.fname,
                 'Current regex: %s' % self.regex,
                 'Current line: %s' % self.line.rstrip('\n'),
                 'Reason: %s' % self.header,
                 'Representation: %s' % repr(self.line),
                 '',
                 'Context:',
                 '']

        linestr = 'L%s:' % self.lineno
        indent = ' ' * len(linestr)
        for line in self.prev_lines:
            lines.append('%s %s' % (indent, line.rstrip('\n')))
        lines.append('%s %s' % (linestr, self.line.rstrip('\n')))
        return '\n'.join(lines)


def devour(pattern, continuation, line, fd, tokens, lines):
    match = pattern.match(line)
    if not match:
        raise ParseError('Current line does not match pattern',
                         regex=pattern.pattern, line=line, prev_lines=lines)
    while match:
        token = match.group('line')
        # Token can "legally" be None for the line 'msgid' (without any ""!)
        if token is not None:
            tokens.append(token)
        lines.append(line)
        line = next(fd)
        match = continuation.match(line)
    return line


class MessageChunk:
    def __init__(self):
        self.lineno = None
        self.is_obsolete = False
        self.comment_lines = []
        self.prevmsgctxt_lines = None
        self.prevmsgid_lines = None
        self.msgctxt_lines = None
        self.msgid_lines = []
        self.msgid_plural_lines = None
        self.msgstrs = []

        self.rawlines = []

    def build(self):
        meta = {'rawlines': self.rawlines,
                'lineno': self.lineno}

        if len(self.msgid_lines) == 0:
            # There is no msgid.  This can only be a chunk of trailing comments
            # Any other chunk would pertain to an actual message.
            trailing_comments = Comments(self.comment_lines,
                                         meta=meta)
            return trailing_comments

        def join(tokens):
            if tokens is None:
                return None
            return ''.join(tokens)

        flags = []
        comments = []

        for line in self.comment_lines:
            if line.startswith('#,'):
                flags.extend(flag.strip() for flag in
                             line[3:].split(','))
            else:
                comments.append(line)

        if self.is_obsolete:
            msgclass = ObsoleteMessage
            for i, comment in enumerate(comments):
                if comment.startswith('#~'):
                    comments[i] = comment[2:].lstrip()
        else:
            msgclass = Message

        msgid = join(self.msgid_lines)
        #msgstr = None
        # If a message has no msgid, then it becomes 'trailing comments'.
        # If it lacks msgstr (even an empty one), this is also an error
        # and we have to handle it well.  Everything else is optional.
        # (However we do not verify number of plurals, etc.  A language with
        # two plurals could have only msgstr[0] and we would not detect this.)
        if len(self.msgstrs) == 0:
            err = PoError('msg-lacks-msgstr',
                          'Message has no msgstr:\n%s'
                          % ''.join(meta['rawlines']))
            err.lineno = meta['lineno']
            raise err
        msgstr = [join(lines) for lines in self.msgstrs]

        if msgid == '':
            charset, headers = parse_header_data(msgstr[0])
            meta['encoding'] = charset
            meta['headers'] = headers

        msg = msgclass(comments=comments,
                       previous_msgctxt=join(self.prevmsgctxt_lines),
                       previous_msgid=join(self.prevmsgid_lines),
                       flags=flags,
                       msgctxt=join(self.msgctxt_lines),
                       msgid=join(self.msgid_lines),
                       msgid_plural=join(self.msgid_plural_lines),
                       msgstr=msgstr,
                       meta=meta)
        return msg


class EchoWrapper:
    def __init__(self, fd):
        self.fd = fd

    def __next__(self):
        line = next(self.fd)
        print(line, end='')
        return line
    next = __next__  # Python2


class FileWrapper:
    def __init__(self, fd):
        self.fd = fd
        self.lineno = 0

    def __next__(self):
        line = None
        while not line or line.isspace():
            line = next(self.fd)
            self.lineno += 1
        if line.endswith('\r\n') or line.endswith('\r'):
            line = line.rstrip('\r\n') + '\n'
        return line
    next = __next__  # Python2


_line_pattern = r'"(?P<line>.*?)"'
# Careful: Always add trailing $ to not match escaped \" within strings


def build_pattern(name):
    # Note: It is actually optional whether a line follows a header
    return regex(r'\s*%s\s*(%s)?\s*$' % (name, _line_pattern))


patterns = {'comment': regex(r'\s*(?P<line>#.*(\n)?)'),
            'prev_msgctxt': build_pattern(r'#\|\s*msgctxt'),
            'prev_msgid': build_pattern(r'#\|\s*msgid'),
            'prev_continuation': build_pattern(r'#\|'),
            'msgctxt': build_pattern('msgctxt'),
            'msgid': build_pattern(r'msgid'),
            'msgid_plural': build_pattern(r'msgid_plural'),
            'msgstr': build_pattern(r'msgstr'),
            'msgstrs': build_pattern(r'msgstr\[[0-9]+\]'),
            'continuation': regex(r'\s*%s\s*$' % _line_pattern)}


obsolete_patterns = {}
for key in patterns:
    obsolete_patterns[key] = regex(r'\s*#~' + patterns[key].pattern)
# We won't bother with prevmsgid in obsoletes!
# This we use a pattern that matches nothing:
obsolete_patterns['prev_msgid'] = regex('.^')


def parse_encoded(fd):
    """Yield all messages in fd.

    The strategy is to go one line at a time, always adding that line
    to a list.  When a new message starts, or there are no more lines,
    yield whatever is there.  Since the function returns at any point
    when there is no line left, don't do any processing here."""

    #fd = EchoWrapper(fd)  # Enable to print all lines
    fd = FileWrapper(fd)

    def _devour(pattern, line, tokens, continuation=None):
        if continuation is None:
            continuation = pat['continuation']
        return devour(pattern, continuation, line, fd, tokens,
                      msg.rawlines)

    prev_msg = None  # We keep this for constructing better errmsgs

    line = next(fd)
    while True:
        msg = MessageChunk()

        # 'pat' will change to another set of patterns if the message
        # turns out to be obsolete
        pat = patterns

        try:
            match = pat['comment'].match(line)
            while match:
                line = match.group('line')
                if obsolete_pattern.match(line) and not msg.is_obsolete:
                    msg.is_obsolete = True
                    pat = obsolete_patterns
                elif pat['prev_msgctxt'].match(line):
                    msg.prevmsgctxt_lines = []
                    line = _devour(pat['prev_msgctxt'],
                                   line, msg.prevmsgctxt_lines,
                                   continuation=pat['prev_continuation'])
                elif pat['prev_msgid'].match(line):
                    msg.prevmsgid_lines = []
                    line = _devour(pat['prev_msgid'],
                                   line, msg.prevmsgid_lines,
                                   continuation=pat['prev_continuation'])
                else:
                    msg.comment_lines.append(line)
                    msg.rawlines.append(line)
                    line = next(fd)
                match = pat['comment'].match(line)

            if pat['msgctxt'].match(line):
                msg.msgctxt_lines = []
                line = _devour(pat['msgctxt'], line, msg.msgctxt_lines)

            msg.lineno = fd.lineno
            line = _devour(pat['msgid'], line, msg.msgid_lines)
            if pat['msgid_plural'].match(line):
                msg.msgid_plural_lines = []
                line = _devour(pat['msgid_plural'], line,
                               msg.msgid_plural_lines)

                while pat['msgstrs'].match(line):
                    lines = []
                    msg.msgstrs.append(lines)
                    line = _devour(pat['msgstrs'], line, lines)
            else:
                lines = []
                msg.msgstrs.append(lines)
                line = _devour(pat['msgstr'], line, lines)

        except StopIteration:
            if msg.lineno is None:
                msg.lineno = fd.lineno
            yield msg.build()
            return
        except ParseError as err:
            if msg.is_obsolete:
                line = next(fd)
                # Should we save the current lines as comments in next msg?
                prev_msg = msg
                continue  # Discard garbage

            err.lineno = fd.lineno
            if prev_msg is not None:
                # Add more lines of context to error message
                err.prev_lines = prev_msg.rawlines + ['\n'] + err.prev_lines
            raise
        else:
            prev_msg = msg
            yield msg.build()


class ReadBuffer:
    def __init__(self, fd):
        self.fd = fd
        self.bytelines = []

    def __next__(self):
        line = next(self.fd)
        self.bytelines.append(line)
        # Python 2.6 does ot accept keyword arguments for decode, the
        # last argument is errors='replace'
        return line.decode('utf8', 'replace')
    next = __next__

    def decode(self, charset):
        return [line.decode(charset) for line in self.bytelines]


def parse_binary(fd):
    """Detect encoding of binary file fd and yield all chunks, encoded."""

    def find_header():
        rbuf = ReadBuffer(fd)
        parser = parse_encoded(rbuf)
        for msg in parser:
            if msg.msgid == '':
                charset, headers = parse_header_data(msg.msgstrs[0])
                return charset, rbuf.bytelines
        raise PoError('no-header',
                      'No header found in file %s' % getfilename(fd))

    # Non-strict parsing to find header and extract charset:
    charset, lines = find_header()

    parser = parse_encoded(iterdecode(itertools.chain(lines, fd),
                                      encoding=charset))

    # Always yield header first.  We buffer the messsages (again) until
    # we find the header, yield the header, then those in the buffer
    msgs = []

    for msg in parser:
        msgs.append(msg)
        if msg.msgid == '':
            break

    yield msgs.pop()
    for msg in msgs:
        yield msg
    for msg in parser:
        yield msg


def iparse(fd, obsolete=True, trailing=True):
    """Parse .po file and yield all Messages.

    The only requirement of fd is that it iterates over lines."""

    msg = None
    try:
        for msg in parse_binary(fd):
            if not msg.is_proper_message and not trailing:
                continue
            if msg.is_obsolete and not obsolete:
                continue
            yield msg
    except PoError as err:
        err.fname = getfilename(fd)
        if err.lineno is None and msg is not None:
            # We could get a better lineno if parse_binary returned
            # something more elaborate
            #
            # Also one could acces its msg and prev_msg
            err.lineno = msg.meta['lineno']
        raise

encoding_pattern = regex(r'[^;]*;\s*charset=(?P<charset>[^\s]+)')


def parse(fd):
    """Parse .po file and return a Catalog.

    Args:
       input (file): A file-like object in binary mode

    Returns:
        Catalog: A message catalog"""

    fname = getfilename(fd)

    msgs = list(iparse(fd))
    assert len(msgs) >= 1
    assert msgs[0].msgid == ''

    trailing_comments = []
    if msgs[-1].msgid is None:
        trailing_comments = msgs.pop()

    encoding = msgs[0].meta['encoding']

    cat = Catalog(fname, encoding, msgs, trailing_comments=trailing_comments)
    return cat


def main():
    from pyg3t.util import get_encoded_output
    out = get_encoded_output('utf-8')
    fname = sys.argv[1]

    with open(fname, 'rb') as fd:
        nmsgs = 0
        cat = parse(fd)
        for msg in cat:
            nmsgs += 1
        print('number of messages: %d' % nmsgs)
        nobs = 0
        for msg in cat.obsoletes:
            nobs += 1
        print('number of obsoletes: %d' % nobs)

        for msg in cat:
            print(msg.tostring(), file=out)
        for msg in cat.obsoletes:
            print(msg.tostring(), file=out)

if __name__ == '__main__':
    main()

# XXX When parsing, allow stuff like:
# * allow for missing header
# * ignore encoding errors
# * ignoring bad syntax
