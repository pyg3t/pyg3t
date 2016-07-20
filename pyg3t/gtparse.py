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

from __future__ import print_function
from __future__ import unicode_literals
from codecs import iterdecode
from pyg3t.util import py2, PoError

import itertools
import re
import sys


def isstringtype(obj):
    return hasattr(obj, 'isalpha')

#from textwrap import TextWrapper
#wrapper = TextWrapper(width=77,
#                      replace_whitespace=False,
#                      expand_tabs=False,
#                      drop_whitespace=False)

# Built-in textwrapper doesn't support the drop_whitespace=False
# option before 2.6, and it's sort of nice to support 2.5 still.
# So this is sort of equivalent to the TextWrapper


def chunkwrap(chunks):
    tokens = []
    chars = 0
    for chunk in chunks:
        if chars + len(chunk) > 77:
            yield ''.join(tokens)
            #lines.append(''.join(tokens))
            tokens = []
            chars = 0
        if len(chunk) > 0:
            tokens.append(chunk)
            chars += len(chunk)
    if tokens:
        yield ''.join(tokens)


wordseparator = re.compile(r'(\s+)')


def wrap(text):
    chunks = iter(wordseparator.split(text))
    return list(chunkwrap(chunks))


def parse_header_data(msgstr):
    headers = {}
    for line in msgstr.split(r'\n'):
        if not line or line.isspace():
            continue  # wtf
        tokens = line.split(':', 1)
        if len(tokens) != 2:
            continue # XXXXXX write warning
        #try:
        key, value = tokens  # Chance of shenanigans?
        #except ValueError:
        #    key = tokens[0]
        #    value = ''  # This should probably not be the case but isn't ugly
            # enough to complain extremely loudly about by default
        #key = key.strip()
        #value = value.strip()
        headers[key.strip()] = value.strip()
    return headers


def _get_header(msgs):
    for msg in msgs:
        if msg.msgid == '':
            msg.meta['headers'] = parse_header_data(msg.msgstr)
            return msg
    else:
        raise ValueError('Header not found in msgs')


class DuplicateMessageError(PoError):
    def __init__(self, msg1, msg2, fname):
        self.msg1 = msg1
        self.msg2 = msg2
        self.fname = fname

    def get_errmsg(self):
        line1 = self.msg1.meta.get('lineno', '<unknown>')
        line2 = self.msg2.meta.get('lineno', '<unknown>')
        linestring1 = 'Message at line %s' % line1
        linestring2 = 'Message at line %s' % line2
        lines = ['Conflicting messages in file %s' % self.fname,
                 'Two messages have identical msgctxt and msgid', '',
                 linestring1, '-' * len(linestring1),
                 self.msg1.tostring(),
                 linestring2, '-' * len(linestring2),
                 self.msg2.tostring()]
        return '\n'.join(lines)


class Catalog(object):
    """A Catalog represents one gettext catalog, or po-file."""
    def __init__(self, fname, encoding, msgs, trailing_comments=None):
        self.fname = fname
        self.encoding = encoding
        _msgs = []
        obsoletes = []
        for msg in msgs:
            if msg.is_obsolete:
                obsoletes.append(msg)
            else:
                _msgs.append(msg)

        self.msgs = _msgs
        self.obsoletes = obsoletes
        self.header = _get_header(self.msgs)
        self.trailing_comments = trailing_comments
        assert 'headers' in self.header.meta

    def dict(self):
        """Return a dict with the contents of this catalog.

        Values are Messages and keys are tuples of (msgid, msgctxt)."""
        d = {}
        for msg in self.msgs:
            key = msg.key
            if key in d:
                raise DuplicateMessageError(d[key], msg, self.fname)
            d[key] = msg
        return d

    def __iter__(self):
        return iter(self.msgs)

    def __len__(self):
        return len(self.msgs)

    def __getitem__(self, index):
        return self.msgs[index]


class Message(object):
    """This class represents a po-file entry.

    Contains attributes that describe:

    * msgid (possibly plural)
    * msgstr(s)
    * comments
    * miscellaneous informations (flags, translation status)"""

    is_obsolete = False

    def __init__(self, msgid, msgstr, msgid_plural=None,
                 msgctxt=None, comments=None, meta=None,
                 flags=None, previous_msgid=None):
        """Create a Message, representing one message from a message catalog.

        Parameters:
         * msgid: string
         * msgstr: string, or list of strings for plurals
         * msgid_plural: None, or a string if there are plurals
         * msgctxt: None, or a string if there is a message context
         * comments: list of newline-terminated strings ([] or None if none)
         * meta: dict of optional metadata (linenumber, raw text from po-file)
         * flags: an iterable of strings specififying flags ('fuzzy', etc.)

         If this message was loaded from a file using the parse() function,
         the meta dictionary will contain the following keys:
          * 'lineno': the original line number of the message in the po-file
          * 'encoding': the encoding of the po-file
          * 'rawlines': the original text in the po-file as a a list of
                        newline-terminated lines

         It is understood that the properties of a Message may be
         changed programmatically so as to render it inconsistent with
         its rawlines and/or lineno.
        """
        self.msgid = msgid
        self.msgid_plural = msgid_plural

        if isstringtype(msgstr):
            self.msgstrs = [msgstr]
        else:
            self.msgstrs = list(msgstr)
        if len(self.msgstrs) > 1:
            assert msgid_plural is not None

        if comments is None:
            comments = []
        self.comments = comments

        # The fuzzy flag is whether fuzzy is specified in the flag
        # comments.  It is ignored if the message has an empty
        # translation.
        if flags is None:
            flags = set()
        self.flags = set(flags)

        self.msgctxt = msgctxt

        # XXX right now the comments are always written as is, even if
        # someone changed the fuzzy flag programmatically.  We should
        # make it so the printed comments will be generated from the
        # programmed representation of the flags
        #
        # XXX Or maybe we already do that?

        self.previous_msgid = previous_msgid
        if meta is None:
            meta = {}
        self.meta = meta

    # Message is either translated, fuzzy or untranslated.
    #
    # If the msgstr (or msgstr[0] in case of plurals) does not have a
    # translation (i.e. it is the empty string), the message is
    # considered untranslated.
    #
    # Else, if the message has the fuzzy flag set, it is considered fuzzy.
    #
    # Else it is considered translated, unless its msgid is empty.
    #
    # This is consistent with msgfmt, but not entirely logical: If a
    # message has multiple plural forms and one of the subsequent ones
    # is not translated, then the message *should* logically be
    # considered untranslated, but this is left for tools like poabc
    # to warn abount.

    @property
    def msgstr(self):
        return self.msgstrs[0]

    @property
    def untranslated(self):
        return self.msgstr == ''

    @property
    def fuzzyflag(self):
        return 'fuzzy' in self.flags

    @property
    def isfuzzy(self):
        return self.fuzzyflag and not self.untranslated

    @property
    def isplural(self):
        return self.msgid_plural is not None

    @property
    def istranslated(self):
        return self.msgstr != '' and not self.fuzzyflag

    @property
    def has_context(self):
        return self.msgctxt is not None

    @property
    def has_previous_msgid(self):
        return self.previous_msgid is not None

    @property
    def key(self):
        return (self.msgid, self.msgctxt)

    def get_comments(self, pattern='', strip=False):
        """Return comments, optionally starting with a particular pattern.

        Returns all the comments for this entry that start with the
        given pattern, useful for extracting, say, translator-comments
        ('# '), previous msgid ('#| msgid ') and so on.  Default pattern
        will return all comment strings.  If strip is True,
        the pattern is removed from the returned strings; otherwise pattern
        is included."""
        striplength = 0
        if strip:
            striplength = len(pattern)
        return [line[striplength:] for line in self.comments
                if line.startswith(pattern)]

    def rawstring(self):
        if 'rawlines' not in self.meta:
            raise KeyError('No raw lines for this Message')
        return ''.join(self.meta['rawlines'])

    def flagstostring(self):
        if self.flags:
            return '#, %s\n' % ', '.join(sorted(self.flags))
        else:
            return ''

    def tostring(self): # maybe add line length argument for wrapping?
        lines = list(self.comments)
        if self.flags:
            lines.append(self.flagstostring())
        if self.has_previous_msgid:
            lines += wrap_declaration('#| msgid', self.previous_msgid,
                                      continuation='#| "')
        if self.has_context:
            lines += wrap_declaration('msgctxt', self.msgctxt)
        lines += wrap_declaration('msgid', self.msgid)
        if self.isplural:
            lines += wrap_declaration('msgid_plural', self.msgid_plural)
            for i, msgstr in enumerate(self.msgstrs):
                lines += wrap_declaration('msgstr[%d]' % i, msgstr)
        else:
            lines += wrap_declaration('msgstr', self.msgstr)
        string = ''.join(lines)
        return string

    def __str__(self):
        string = self.tostring()
        if py2:
            string = string.encode('utf-8')
        return string

    def copy(self):
        return self.__class__(self.msgid, self.msgstrs, self.msgid_plural,
                              msgctxt=self.msgctxt,
                              comments=list(self.comments),
                              meta=self.meta.copy(), flags=self.flags.copy())

# XXXXXXX get previous msgctxt at some point, #| msgctxt "..."

    #def decode(self):
    #    encoding = self.meta['encoding']
    #    msgvars = vars(self)

    #    kwargs = {}
    #    for key in ['comments', 'msgstrs', 'flags']:
    #        kwargs[key] = [string.decode(encoding) for string in msgvars[key]]
    #    kwargs['msgstr'] = kwargs.pop('msgstrs')
    #    for key in ['msgid', 'msgid_plural', 'msgctxt']:
    #        if msgvars[key] is None:
    #            kwargs[key] = None
    #        else:
    #            kwargs[key] = msgvars[key].decode(encoding)
    #    meta = msgvars['meta'].copy()
    #    kwargs['meta'] = meta
    #    return self.__class__(**kwargs)


class ObsoleteMessage(Message):

    is_obsolete = True

    def tostring(self):
        string = Message.tostring(self)
        lines = []

        # And now the ugliest hack in the history of computing
        #
        # Anything that doesn't already have a '#~ ' in front of it gets
        # one now.
        for line in string.splitlines():
            if not line.startswith('#~'):
                line = '#~ %s' % line
            lines.append(line)
        lines.append('') # to get an extra newline
        # XXX does not re-wrap if line is too long
        return '\n'.join(lines)


# Yuck!!
# XXXXX We need a special case for the chunk of comments that sometimes
# loafs unwelcomely at EOF.
# This will likely cause lots of trouble.
class TrailingComments(ObsoleteMessage):
    def tostring(self):
        return ''.join(comment for comment in self.comments)


def is_wrappable(declaration, string):
    if len(string) + len(declaration) > 75:
        return True
    newlineindex = string.find(r'\n')

    # Don't wrap if newline is only at end of string
    if newlineindex > 0 and not newlineindex == len(string) - 2:
        return True
    return False


def wrap_declaration(declaration, string, continuation='"', end='"\n'):
    if is_wrappable(declaration, string):
        tokens = []
        tokens.append('%s ""\n' % declaration)
        # XXX this will make a newline in the case \\n also
        linetokens = string.split(r'\n')
        for i, token in enumerate(linetokens[:-1]):
            linetokens[i] += r'\n' # grrr
        for linetoken in linetokens:
            lines = wrap(linetoken)
            for line in lines:
                tokens.append(continuation)
                tokens.append(line)
                tokens.append(end)
        return tokens #''.join(tokens)
    else:
        return ['%s "%s"\n' % (declaration, string)]

#---------------------------------------------------

obsolete_pattern = re.compile(r'\s*#~')
obsolete_extraction_pattern = re.compile(r'\s*#~\s*(?P<line>.*)')

# Content-Type should generally be text/plain
# TODO Issue warning otherwise.
charset_extraction_pattern = re.compile(r'^Content-Type:\s*[^;]*;'
                                        r'\s*charset=(?P<charset>[^\\]*)')


def get_charset(header_msgstr_lines):
    for line in header_msgstr_lines:
        match = charset_extraction_pattern.match(line)
        if match:
            charset = match.group('charset')
            return charset


class ParseError(PoError):
    def __init__(self, header, regex, line, prev_lines):
        self.header = header
        self.regex = regex
        self.line = line
        self.prev_lines = prev_lines
        self.lineno = '<unknown>'
        self.fname = '<unknown>'
        super(ParseError, self).__init__()

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
        raise ParseError('Current line does not match regex',
                         regex=pattern.pattern, line=line, prev_lines=lines)
    while match:
        token = match.group('line')
        if token is None:
            raise ParseError('Line matches regex but extracts nothing.'
                             '  This is an internal error.  Please report it.',
                             regex=match.re.pattern, line=line,
                             prev_lines=lines)
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
        self.prevmsgid_lines = None
        self.msgctxt_lines = None
        self.msgid_lines = []
        self.msgid_plural_lines = None
        self.msgstrs = []

        self.rawlines = []

    def __iter__(self):
        lists = [self.comment_lines, self.msgctxt_lines, self.msgid_lines,
                 self.msgid_plural_lines] + self.msgstrs
        for _list in lists:
            if _list is None:
                continue
            for line in _list:
                yield line

    def get_msgid(self):
        if not self.msgid_lines:
            return None
        return ''.join(self.msgid_lines)


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


patterns = {'comment': re.compile(r'\s*(?P<line>#.*)'),
            'prev_msgid': re.compile(r'\s*#\|\s*msgid\s*"(?P<line>.*?)"\s*$'),
            'prev_msgid_continuation': re.compile(r'\s*#\|\s*"(?P<line>.*?)"\s*$'),
            'msgctxt': re.compile(r'\s*msgctxt\s*"(?P<line>.*?)"\s*$'),
            'msgid': re.compile(r'\s*msgid\s*"(?P<line>.*?)"\s*$'),
            'msgid_plural': re.compile(r'\s*msgid_plural'
                                       r'\s*"(?P<line>.*?)"\s*$'),
            'msgstr': re.compile(r'\s*msgstr\s*"(?P<line>.*?)"\s*$'),
            'msgstrs': re.compile(r'\s*msgstr\[[0-9]*\]'
                                  r'\s*"(?P<line>.*?)"\s*$'),
            'continuation': re.compile(r'\s*"(?P<line>.*?)"\s*$')}

obsolete_patterns = {}
for key in patterns:
    obsolete_patterns[key] = re.compile(r'\s*#~' + patterns[key].pattern)
# We won't bother with prevmsgid in obsoletes!
# This we use a pattern that matches nothing:
obsolete_patterns['prev_msgid'] = re.compile('.^')

def lowlevel_parse_encoded(fd):
    """Yield all chunks in fd, where fd must have correct encoding."""

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
            while pat['comment'].match(line):
                if obsolete_pattern.match(line) and not msg.is_obsolete:
                    msg.is_obsolete = True
                    pat = obsolete_patterns
                elif pat['prev_msgid'].match(line):
                    msg.prevmsgid_lines = []
                    line = _devour(pat['prev_msgid'],
                                   line, msg.prevmsgid_lines,
                                   continuation=pat['prev_msgid_continuation'])
                else:
                    msg.comment_lines.append(line)
                    line = next(fd)

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
            yield msg
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
            yield msg


class ReadBuffer:
    def __init__(self, fd):
        self.fd = fd
        self.bytelines = []

    def __next__(self):
        line = next(self.fd)
        self.bytelines.append(line)
        return line.decode('utf8', errors='replace')
    next = __next__

    def decode(self, charset):
        return [line.decode(charset) for line in self.bytelines]

def lowlevel_parse_binary(fd):
    """Detect encoding of binary file fd and yield all chunks, encoded."""

    def find_header():
        rbuf = ReadBuffer(fd)
        parser = lowlevel_parse_encoded(rbuf)
        for msg in parser:
            if msg.get_msgid() == '':
                charset = get_charset(msg.msgstrs[0])
                return charset, rbuf.bytelines
        raise PoError('No header found in file %s' % fd.name)

    # Non-strict parsing to find header and extract charset:
    try:
        charset, lines = find_header()

        parser = lowlevel_parse_encoded(iterdecode(itertools.chain(lines, fd),
                                                   encoding=charset))

        for msg in parser:
            yield msg
    except ParseError as err:
        err.fname = fd.name
        raise


def iterparse(fd):
    trailing_comments = None

    for chunk in lowlevel_parse_binary(fd):
        flags = []
        comments = []

        meta={'rawlines': chunk.rawlines,
              'lineno': chunk.lineno}

        # We should not do any more loops after we get the trailing comments
        assert trailing_comments is None

        if len(chunk.msgid_lines) == 0:
            # There is no msgid.  This can only be a chunk of trailing comments
            # Any other chunk would pertain to an actual message.
            trailing_comments = TrailingComments(msgid=None,
                                                 msgstr='',
                                                 comments=chunk.comment_lines,
                                                 meta=meta)
            yield trailing_comments
            continue

        for line in chunk.comment_lines:
            if line.startswith('#,'):
                flags.extend(flag.strip() for flag in
                             line[3:].split(','))
            else:
                comments.append(line)

        def join(tokens):
            if tokens is None:
                return None
            return ''.join(tokens)

        if chunk.is_obsolete:
            msgclass = ObsoleteMessage
        else:
            msgclass = Message

        msgstr = None
        if len(chunk.msgstrs) > 0:
            msgstr = [join(lines) for lines in chunk.msgstrs]

        msg = msgclass(comments=comments,
                       previous_msgid=join(chunk.prevmsgid_lines),
                       flags=flags,
                       msgctxt=join(chunk.msgctxt_lines),
                       msgid=join(chunk.msgid_lines),
                       msgid_plural=join(chunk.msgid_plural_lines),
                       msgstr=msgstr,
                       meta=meta)
        yield msg


encoding_pattern = re.compile(r'[^;]*;\s*charset=(?P<charset>[^\s]+)')


def parse(fd):
    try:
        fname = fd.name
    except AttributeError:
        fname = '<unknown>'

    msgs = []

    for msg in iterparse(fd):
        if msg.msgid == '':
            msgs.insert(0, msg)
        else:
            msgs.append(msg)

    assert len(msgs) >= 1
    assert msgs[0].msgid == ''

    trailing_comments = []
    if msgs[-1].msgid is None:
        trailing_comments = msgs.pop().comments

    headers = parse_header_data(msgs[0].msgstr)
    encoding_line = headers['Content-Type']
    match = re.match(encoding_pattern, encoding_line)
    assert match is not None, (encoding_pattern.pattern, encoding_line)
    encoding = match.group('charset')

    cat = Catalog(fname, encoding, msgs, trailing_comments=trailing_comments)
    return cat


def main():
    from pyg3t.util import get_encoded_stdout
    out = get_encoded_stdout('utf-8')
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
