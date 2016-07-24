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
from pyg3t.charsets import get_normalized_encoding_name
import itertools
import re
import sys

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


# It is recommended that the license should be the first comment in each source
# code file, but it doesn't make a good module level doc string, so supply one
# manually

__doc__ = """
The gtparse module contains the basic functionality to parse
:term:`gettext catalog` s (.po files). The most important items are:

 * The :py:func:`.parse` function, which parses an entire gettext catalog from
   a file. **This function is the main entry point for the module**.
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


def isstringtype(obj):
    return hasattr(obj, 'isalpha')


def chunkwrap(chunks):
    """Returns a generator of lines, from the content in :term:`chunk` s,
    wrapped to a max length of 77 characters.

    Similar in functionality to:

    .. code-block:: python

       textwrapper.TextWrapper(width=77,
                               replace_whitespace=False,
                               expand_tabs=False,
                               drop_whitespace=False)

    but since TextWrapper in Python 2.5 does not support the
    ``drop_whitespace=False`` option, this implementation is used until
    support for Python 2.5 is dropped.

    Args:
        chunks (iterable): :term:`Chunk` s of text to wrap
    """
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


def wrap(text, wordsep=re.compile(r'(\s+)')):
    """Wrap text to 77 characters and return as list of lines."""
    chunks = iter(wordsep.split(text))
    return list(chunkwrap(chunks))


# Content-Type should generally be text/plain
# TODO Issue warning otherwise.
#charset_extraction_pattern = re.compile(r'^Content-Type:\s*[^;]*;'
#                                        r'\s*charset=(?P<charset>[^\\]*)')
charset_extraction_pattern = re.compile(r'[^;]*;'
                                        r'\s*charset=(?P<charset>[^\\]*)')


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
        raise PoError('Content-Type not in headers: %s' % headers)
    match = charset_extraction_pattern.match(headers['Content-Type'])
    if not match:
        raise PoError('Cannot extract charset from header "%s"' %
                      headers['Content-Type'])

    # Normalize charset
    charset_string = match.group('charset')
    try:
        charset = get_normalized_encoding_name(charset_string)
    except LookupError as err:
        raise PoError('Charset not recognized: %s' % str(err))

    # Extract more info?
    return charset, headers


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
    """A Catalog represents one gettext catalog, or po-file.

    Args:
        fname (string): Filename of the source
        encoding (string): The encoding of the source
        msgs (iterable): Iterable of :py:class:`.Message` or
            :py:class:`.ObsoleteMessage`

    Attributes:
        fname (str): The filename of the source
        encoding (str): The encoding of the source
        msgs (list): The list of messages (:py:class:`.Message`) in the
            catalog
        obsoletes (list): The list of obsolete messages
            (:py:class:`.ObsoleteMessage`) in the catalog
        trailing_comments (list of strings): Trailing comments after messages
    """
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
        assert self.msgs[0].msgid == ''
        self.headers = self.msgs[0].meta['headers']
        self.trailing_comments = trailing_comments
        #assert 'headers' in self.header.meta

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
        """Return an iterator of the (non-obsolete) messages."""
        return iter(self.msgs)

    def __len__(self):
        """Return the number of (non-obsolete) messages."""
        return len(self.msgs)

    def __getitem__(self, index):
        """Return an item by index among (non-obsolete) messages."""
        return self.msgs[index]


class Message(object):
    """This class represents a :term:`message` in a :term:`gettext catalog`

    Parameters:
        msgid (string): The :term:`msgid`
        msgstr (string or list): The translated :term:`msgstr` s
        msgid_plural (string): msgid plural if any, otherwise None
        msgctxt (string): Context message of any, otherwise None
        comments (list): Newline-terminated strings (or None if none)
                         Comments should include #.  They should not include
                         lines that specify flags or previous msgid/msgctxt.
        meta (dict): Optional metadata (linenumber, raw text from po-file)
        flags (iterable): Strings specififying flags ('fuzzy', etc.)
        previous_msgid: None, or a string if there is a previous msgid.
        previous_msgctxt: None, or a string if there is a previous msgctxt.

    If this message was loaded from a file using the parse() function,
    the meta dictionary will contain the following keys:

     * 'lineno': the original line number of the message in the po-file
     * 'encoding': the encoding of the po-file
     * 'rawlines': the original text in the po-file as a a list of
       newline-terminated lines

     It is understood that the properties of a Message may be
     changed programmatically so as to render it inconsistent with
     its rawlines and/or lineno.

    Attributes:
        msgid (str): The :term:`msgid`
        msgid_plural (str): The plural msgid if any, otherwise None
        msgstr (list): The translated :term:`msgstr` s
        comments (list): Newline terminated comments strs
        msgctxt (str): The msgid context if any, otherwise None
        flags (set): Flags (strs) that are set if they are present
        previous_msgid (str): The previous msgid if any, otherwise None
        is_obsolete (bool): Whether the message is obsolete
        meta (dict): The metadata dictionary
    """

    is_obsolete = False

    def __init__(self, msgid, msgstr, msgid_plural=None,
                 msgctxt=None, comments=None, meta=None,
                 flags=None, previous_msgctxt=None, previous_msgid=None):
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

        self.previous_msgctxt = previous_msgctxt
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
        """The :term:`msgstr`, or first translation in case of plurals."""
        return self.msgstrs[0]

    @property
    def untranslated(self):
        """Whether the message is untranslated."""
        return self.msgstr == ''

    @property
    def fuzzyflag(self):
        """Whether the :term:`fuzzy` flag is set."""
        return 'fuzzy' in self.flags

    @property
    def isfuzzy(self):
        """Whether the message is :term:`fuzzy`."""
        return self.fuzzyflag and not self.untranslated

    @property
    def isplural(self):
        """Whether the message has plurals."""
        return self.msgid_plural is not None

    @property
    def istranslated(self):
        """Whether the message is translated."""
        return self.msgstr != '' and not self.fuzzyflag

    @property
    def has_context(self):
        """Whether the message has context."""
        return self.msgctxt is not None

    @property
    def has_previous_msgctxt(self):
        return self.previous_msgctxt is not None

    @property
    def has_previous_msgid(self):
        """Whether the message has a previous msgid."""
        return self.previous_msgid is not None

    @property
    def key(self):
        """The tuple (msgid, msgctxt).

        This can be considered a unique (within the catalog) key for use e.g.
        in a dict."""
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
        """Get original text for this message.

        Returns the original text :term:`chunk` that this message was parsed
        from, as a string.

        Returns:
            (string): The original raw text chunk

        Raises:
            KeyError: If there are no raw lines in the metadata"""
        if 'rawlines' not in self.meta:
            raise KeyError('No raw lines for this Message')
        return ''.join(self.meta['rawlines'])

    def flagstostring(self):
        """Return a flag string on the form: ``"#, flag0, flag1, ...\\n"``."""
        if self.flags:
            return '#, %s\n' % ', '.join(sorted(self.flags))
        else:
            return ''

    def tostring(self): # maybe add line length argument for wrapping?
        """Return :term:`gettext catalog` string form of this message.

        The string will be on the form. First all comments that are not
        previous msgid (if any), then the flags (if any), then the previous
        msgid (if any), then the context (if any) and finnaly the :term:`msgid`
        and the :term:`msgstr`.

        .. code-block:: po

            #  translator-comments
            #. extracted-comments
            #: reference...
            #, flag...
            #| msgctxt previous-context
            #| msgid previous-untranslated-string
            msgctxt context
            msgid untranslated-string
            msgstr translated-string

        Example from the `gettext reference documentation
        <http://www.gnu.org/software/gettext/manual/html_node/PO-Files.html>`_
        """
        lines = list(self.comments)
        if self.flags:
            lines.append(self.flagstostring())
        if self.has_previous_msgctxt:
            lines += wrap_declaration('#| msgctxt', self.previous_msgctxt,
                                      continuation='#| "')
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
        """Return a copy of this message."""
        return self.__class__(self.msgid, self.msgstrs,
                              msgid_plural=self.msgid_plural,
                              msgctxt=self.msgctxt,
                              comments=list(self.comments),
                              meta=self.meta.copy(), flags=self.flags.copy(),
                              previous_msgctxt=self.previous_msgctxt,
                              previous_msgid=self.previous_msgid)


class ObsoleteMessage(Message):
    """Represents an obsolete :term:`message` in a :term:`gettext catalog`."""

    is_obsolete = True

    def tostring(self):
        """Return :term:`gettext catalog` string form of this obsolete message.

        This string is on the form described in :py:meth:`.Message.tostring`
        where all lines that does not already start with an '#~' gets it
        prepended."""

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
    """Return whether a declaration should be wrapped into multiple lines.

    See :py:func:`.wrap_declaration` for details on the arguments."""
    if len(string) + len(declaration) > 75:
        return True
    newlineindex = string.find(r'\n')

    # Don't wrap if newline is only at end of string
    if newlineindex > 0 and not newlineindex == len(string) - 2:
        return True
    return False


def wrap_declaration(declaration, string, continuation='"', end='"\n'):
    """Return the declaration followed by a wrapped form of the string

    .. note:: The wrapping takes place linewise and the splitting of lines
        respects escaped newlines. This is done in an attempt to preserve the
        visual presentation of the string

    If the declaration and the string will not fit in a single line, the
    declaration if left on a line for itself, followed merely by an empty
    string.

    Example:

    .. code-block:: po

        msgid "This is a short msgid"

        msgid ""
        "This is a msgid with a very long msgid, in fact it just keeps going "
        "and going and going.

    Args:
        declaration (str): A declaration in a :term:`message` such as msgid,
            msgstr or msgctxt
        string (str): The string to wrap i.e. the content of the declaration

    Returns:
        str: The declaration followed by a wraped for of the string
    """
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

obsolete_pattern = re.compile(r'\s*#~')
obsolete_extraction_pattern = re.compile(r'\s*#~\s*(?P<line>.*)')


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
            trailing_comments = TrailingComments(msgid=None,
                                                 msgstr='',
                                                 comments=self.comment_lines,
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
        else:
            msgclass = Message

        msgid = join(self.msgid_lines)
        msgstr = None
        if len(self.msgstrs) > 0:
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
    return re.compile(r'\s*%s\s*(%s)?\s*$' % (name, _line_pattern))


patterns = {'comment': re.compile(r'\s*(?P<line>#.*)'),
            'prev_msgctxt': build_pattern(r'#\|\s*msgctxt'),
            'prev_msgid': build_pattern(r'#\|\s*msgid'),
            'prev_continuation': build_pattern(r'#\|'),
            'msgctxt': build_pattern('msgctxt'),
            'msgid': build_pattern(r'msgid'),
            'msgid_plural': build_pattern(r'msgid_plural'),
            'msgstr': build_pattern(r'msgstr'),
            'msgstrs': build_pattern(r'msgstr\[[0-9]+\]'),
            'continuation': re.compile(r'\s*%s\s*$' % _line_pattern)}


obsolete_patterns = {}
for key in patterns:
    obsolete_patterns[key] = re.compile(r'\s*#~' + patterns[key].pattern)
# We won't bother with prevmsgid in obsoletes!
# This we use a pattern that matches nothing:
obsolete_patterns['prev_msgid'] = re.compile('.^')

def parse_encoded(fd):
    """Yield all messages in fd.

    The strategy is to go one line at a time, always adding that line
    to a list.  When a new message starts, or there are no more lines,
    yield whatever is there."""

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
        return line.decode('utf8', errors='replace')
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
                #msg.meta['charset'] = charset
                #msg.meta['headers'] = header
                return charset, rbuf.bytelines
        raise PoError('No header found in file %s' % getfilename(fd))

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


def iparse(fd):
    """Parse .po file and yield all Messages.

    The only requirement of fd is that it iterates over lines."""
    # Can we add more info to exceptions?
    try:
        for msg in parse_binary(fd):
            yield msg
    except ParseError as err:
        err.fname = getfilename(fd)
        raise

encoding_pattern = re.compile(r'[^;]*;\s*charset=(?P<charset>[^\s]+)')


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
        trailing_comments = msgs.pop().comments

    encoding = msgs[0].meta['encoding']

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
