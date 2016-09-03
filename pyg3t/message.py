from __future__ import print_function, unicode_literals

from pyg3t.util import py2, PoError, noansi, ansipattern, ansi_nocolor, regex


class DuplicateMessageError(PoError):
    def __init__(self, msg1, msg2, fname):
        self.msg1 = msg1
        self.msg2 = msg2
        self.fname = fname
        super(DuplicateMessageError, self).__init__('duplicate-msg')

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


def isstringtype(obj):
    return hasattr(obj, 'isalpha')


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

    def dict(self, obsolete=False):
        """Return a dict with the contents of this catalog.

        Values are Messages and keys are tuples of (msgid, msgctxt)."""
        d = {}

        for msg in self.iter(trailing=False, obsolete=obsolete):
            key = msg.key
            if key in d:
                raise DuplicateMessageError(d[key], msg, self.fname)
            d[key] = msg
        return d

    def __iter__(self):
        """Return an iterator of the (non-obsolete) messages."""
        return iter(self.msgs)

    def iter(self, msgs=True, obsolete=True, trailing=True):
        """Return iterator over all or some parts of the catalog."""
        if msgs:
            for msg in self.msgs:
                yield msg
        if obsolete:
            for msg in self.obsoletes:
                yield msg
        if trailing and self.trailing_comments is not None:
            yield self.trailing_comments

    def __len__(self):
        """Return the number of (non-obsolete) messages."""
        return len(self.msgs)

    def __getitem__(self, index):
        """Return an item by index among (non-obsolete) messages."""
        return self.msgs[index]


class Message(object):
    """This class represents a :term:`message` in a :term:`gettext catalog`

    Parameters:
        comments (list): Newline-terminated strings starting with '#'.
                         Do not include flags (#,) or previous
                         msgid/msgctxt (#|)
        previous_msgctxt (string or None): Old msgctxt (#| msgctxt) if present.
        previous_msgid (string or None): Old msgid (#| msgid) if present.
        flags (set of strings): Flags ('fuzzy', 'c-format', etc.)
        msgctxt (string or None): Context if present
        msgid (string): The :term:`msgid`
        msgstrs (list of strings): The translated :term:`msgstr` s
        msgid_plural (string or None): msgid plural if present
        meta (dict): Optional metadata (linenumber, raw text from po-file)

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
    is_proper_message = True

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

    def flagstostring(self, colorize=lambda string: string):
        """Return a flag string on the form ``"#, flag0, flag1, ...\\n"``."""
        if not self.flags:
            return ''
        return '%s %s\n' % (colorize('#,'),
                            ', '.join(f for f in sorted(self.flags)))

    def tostring(self, colorize=lambda string: string):
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
        c = colorize

        lines = list(self.comments)
        lines.append(self.flagstostring(c))
        if self.has_previous_msgctxt:
            lines += wrap_declaration('%s %s' % (c('#|'), c('msgctxt')),
                                      self.previous_msgctxt,
                                      continuation=c('#|') + ' "')
        if self.has_previous_msgid:
            lines += wrap_declaration('%s %s' % (c('#|'), c('msgid')),
                                      self.previous_msgid,
                                      continuation=c('#|') + ' "')
        if self.has_context:
            lines += wrap_declaration(c('msgctxt'), self.msgctxt)
        lines += wrap_declaration(c('msgid'), self.msgid)
        if self.isplural:
            lines += wrap_declaration(c('msgid_plural'), self.msgid_plural)
            for i, msgstr in enumerate(self.msgstrs):
                lines += wrap_declaration(c('msgstr[%d]') % i, msgstr)
        else:
            lines += wrap_declaration(c('msgstr'), self.msgstr)
        return ''.join(lines)

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

    def tostring(self, colorize=lambda string: string):
        """Return :term:`gettext catalog` string form of this obsolete message.

        This string is on the form described in :py:meth:`.Message.tostring`
        where all lines that does not already start with an '#~' gets it
        prepended."""

        string = super(ObsoleteMessage, self).tostring(colorize=colorize)
        lines = []

        for line in string.splitlines():
            line = '%s %s' % (colorize('#~'), line)
            lines.append(line)
        lines.append('') # to get an extra newline
        # XXX does not re-wrap if line is too long
        return '\n'.join(lines)


# Yuck!!
# XXXXX We need a special case for the chunk of comments that sometimes
# loafs unwelcomely at EOF.
# This will likely cause lots of trouble.
class Comments:
    is_proper_message = False
    is_obsolete = False

    def __init__(self, comments, meta=None):
        self.comments = comments
        self.previous_msgctxt = None
        self.previous_msgid = None
        self.msgctxt = None
        self.msgid = None
        self.msgid_plural = None
        self.msgstrs = []
        self.meta = meta if meta is not None else {}

    def tostring(self, colorize=None):
        return ''.join(comment for comment in self.comments)


def chunkwrap(chunks):
    """Returns a generator of lines, from the content in :term:`chunk` s,
    wrapped to a max length of 77 characters.

    Similar in functionality to:

    .. code-block:: python

       textwrapper.TextWrapper(width=77,
                               replace_whitespace=False,
                               expand_tabs=False,
                               drop_whitespace=False)

    but we would have to somehow hack the built-in textwrapper to take
    declarations like msgid_plural into account, or add and remove paddings
    in funny ways to pre/postprocess its output.

    Args:
        chunks (iterable): :term:`Chunk` s of text to wrap
    """
    tokens = []
    chars = 0

    for chunk in chunks:
        chunklen = len(noansi(chunk))
        if chars + chunklen > 77:
            yield ''.join(tokens)

            tokens = []
            chars = 0
        if chunklen > 0:
            tokens.append(chunk)
            chars += chunklen
    if tokens:
        yield ''.join(tokens)


def wrap(text, wordsep=regex(r'(\s+)')):
    """Wrap text to 77 characters and return as list of lines."""
    tokens = wordsep.split(text)
    chunks = iter(tokens)
    return list(chunkwrap(chunks))


def is_wrappable(declaration, string, maxwidth=77):
    """Return whether a declaration should be wrapped into multiple lines.

    See :py:func:`.wrap_declaration` for details on the arguments."""
    declaration = noansi(declaration)
    string = noansi(string)

    if len(string) + len(declaration) > maxwidth - 2:
        return True
    newlineindex = string.find(r'\n')

    # Don't wrap if newline is only at end of string
    if newlineindex > 0 and not newlineindex == len(string) - 2:
        return True
    return False


def newwrap(tokens, maxwidth=77, endline=r'\n'):
    """Group a list of tokens into a list of lists of tokens.

    This function is ANSI-color aware.  ANSI color patterns will be
    detected and added when appropriate to ensure that coloring
    terminates at the end of each line, and starts at next line."""
    nchars = 0
    lines = []
    line = []

    current_color = ansi_nocolor
    for token in tokens:
        if len(token) == 0:
            continue
        colors = ansipattern.findall(token)
        if colors:
            current_color = colors[-1]
        tokenlen = len(noansi(token))
        if nchars + tokenlen > maxwidth:
            if current_color != ansi_nocolor:
                # Switch off color before ending line.
                # We must remember color at beginning of next line
                line.append(ansi_nocolor)
            lines.append(line)
            nchars = 0
            line = []
            if current_color != ansi_nocolor:
                # Remember color at beginning of next line
                line.append(current_color)
        nchars += tokenlen
        line.append(token)
        if token.endswith(endline):  # We could accept a pattern here
            nchars = maxwidth  # This ensures break before next token if any
    lines.append(line)
    return lines

# Split over any number of letters followed by either newline or whitespace
linetoken_pattern = regex(r'(\S*?(?:\\n|\s+))')


def wrap_declaration(declaration, string, continuation='"', end='"\n',
                     maxwidth=77):
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
    if is_wrappable(declaration, string, maxwidth=maxwidth):
        lines = newwrap(linetoken_pattern.split(string), maxwidth=maxwidth)

        tokens = ['%s ""\n' % declaration]
        for line in lines:
            tokens.append(continuation)
            tokens.extend(line)
            tokens.append(end)
        return tokens
    else:
        return ['%s "%s"\n' % (declaration, string)]
