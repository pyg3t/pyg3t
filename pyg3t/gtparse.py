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

import re

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

def parse_header_data(msg):
    headers = {}
    for line in msg.msgstr.split(r'\n'):
        if not line or line.isspace():
            continue
        tokens = line.split(':', 1)
        try:
            key, value = tokens
        except ValueError:
            key = tokens[0]
            value = '' # This should probably not be the case but isn't ugly
            # enough to complain extremely loudly about by default
        key = key.strip()
        value = value.strip()
        headers[key] = value
    return headers

def _get_header(msgs):
    for msg in msgs:
        if msg.msgid == '':
            msg.meta['headers'] = parse_header_data(msg)
            return msg
    else:
        raise ValueError('header not found in msgs')


class Catalog(object):
    """A Catalog represents one gettext catalog, or po-file."""
    def __init__(self, fname, encoding, msgs):
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
        assert 'headers' in self.header.meta

    def dict(self):
        """Return a dict with the contents of this catalog.

        Values are Messages and keys are tuples of (msgid, msgctxt)."""
        d = {}
        for msg in self.msgs:
            d[msg.key] = msg
        return d
    
    def obsoletes(self):
        return iter(self.obsoletes)

    def __iter__(self):
        return iter(self.msgs)

    def __len__(self):
        return len(self.msgs)

    def __getitem__(self, index):
        return self.msgs[index]
    
    def decode(self):
        # XXX not really implemented
        msgs = [msg.decode() for msg in self]
        obsoletes = [obs.decode() for obs in self.obsoletes]
        cat = Catalog(self.fname, self.encoding, msgs + obsoletes)
        return cat

    def encode(self, encoding=None):
        # XXX not really implemented
        if encoding is None:
            encoding = self.encoding
        msgs = [msg.encode(encoding) for msg in self]
        obsoletes = [obs.encode(encoding) for obs in self.obsoletes]
        cat = Catalog(self.fname, encoding, msgs, obsoletes)
        return cat

    def _catalog(self, msgs, obsoletes=None):
        cat = Catalog(self.fname, self.encoding, msgs, obsoletes)
        return cat

    def filter(self, choicefunction):
        return self._catalog(msg for msg in self if choicefunction(msg))

    def get_translated(self):
        return self.filter(Message.istranslated)
    
    def get_untranslated(self):
        return self.filter(Message.untranslated)
    
    def get_fuzzy(self):
        return self.filter(Message.isfuzzy)


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

        if isinstance(msgstr, basestring):
            assert msgid_plural is None
            self.msgstrs = [msgstr]
        else:
            self.msgstrs = list(msgstr)
        
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
    def istranslated(self):
        return self.msgstr != '' and not self.fuzzyflag
    
    @property
    def has_context(self):
        return self.msgctxt is not None
    
    @property
    def has_previous_msgid(self):
        return self.previous_msgid is not None
    
    @property
    def hasplurals(self):
        return self.msgid_plural is not None

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
        if not 'rawlines' in self.meta:
            raise KeyError('No raw lines for this Message')
        return ''.join(self.meta['rawlines'])

    def flagstostring(self):
        if self.flags:
            return '#, %s\n' % ', '.join(sorted(self.flags))
        else:
            return ''

    def tostring(self): # maybe add line length argument for wrapping?
        lines = []
        lines.extend([c for c in self.comments if not c.startswith('#|')])
        if self.flags:
            lines.append(self.flagstostring())
        lines.extend([c for c in self.comments if c.startswith('#|')])
        if self.has_context:
            lines.append(wrap_declaration('msgctxt', self.msgctxt))
        lines.append(wrap_declaration('msgid', self.msgid))
        if self.hasplurals:
            lines.append(wrap_declaration('msgid_plural', self.msgid_plural))
            for i, msgstr in enumerate(self.msgstrs):
                lines.append(wrap_declaration('msgstr[%d]' % i, msgstr))
        else:
            lines.append(wrap_declaration('msgstr', self.msgstr))
        string = ''.join(lines)
        return string

    def __str__(self):
        return self.tostring()

    def copy(self):
        return self.__class__(self.msgid, self.msgstrs, self.msgid_plural,
                              msgctxt=self.msgctxt, 
                              comments=list(self.comments),
                              meta=self.meta.copy(), flags=self.flags.copy())

    def decode(self):
        encoding = self.meta['encoding']
        msgvars = vars(self)
        
        kwargs = {}
        for key in ['comments', 'msgstrs', 'flags']:
            kwargs[key] = [string.decode(encoding) for string in msgvars[key]]
        kwargs['msgstr'] = kwargs.pop('msgstrs')
        for key in ['msgid', 'msgid_plural', 'msgctxt']:
            if msgvars[key] is None:
                kwargs[key] = None
            else:
                kwargs[key] = msgvars[key].decode(encoding)
        meta = msgvars['meta'].copy()
        meta['representation'] = 'unicode'
        kwargs['meta'] = meta
        return self.__class__(**kwargs)

    def check(self):
        if self.meta.get('representation') == 'unicode':
            stringtype = unicode
        else:
            stringtype = basestring
        assert isinstance(self.msgid, stringtype)
        for msgstr in self.msgstrs:
            assert isinstance(msgstr, stringtype)
        assert self.msgid_plural is None or isinstance(self.msgid_plural, 
                                                       stringtype)


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
        

def is_wrappable(declaration, string):
    if len(string) + len(declaration) > 75:
        return True
    newlineindex = string.find(r'\n')
    
    # Don't wrap if newline is only at end of string
    if newlineindex > 0 and not newlineindex == len(string) - 2:
        return True
    return False


def wrap_declaration(declaration, string):
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
                tokens.append('"')
                tokens.append(line)
                tokens.append('"\n')
        return ''.join(tokens)
    else:
        return '%s "%s"\n' % (declaration, string)


class LineNumberIterator:
    # XXX Can probably be replaced by using fileinput module
    def __init__(self, input):
        self.lineno = 0
        self.input = input
        self.lines = []
        self.iter = iter(self)
        self.last_lines = []
        self.max_last_lines = 12
    
    def pop_lines(self):
        lines = self.lines
        self.lines = []
        return lines

    def __iter__(self):
        for line in self.input:
            self.lineno += 1
            self.last_lines.append(line)
            if len(self.last_lines) > self.max_last_lines:
                self.last_lines.pop(0)
            if line.isspace():
                continue
            yield line

    def next(self):
        return self.iter.next()


class PoHeaderError(ValueError):
    pass


class PoError(ValueError):
    """Error raised by the parser containing user-friendly error messages."""
    def __init__(self, errmsg, fname=None, lineno=None,
                 original_error=None,
                 last_lines=None):
        ValueError.__init__(self, errmsg)
        self.errmsg = errmsg
        self.fname = fname
        self.lineno = lineno
        self.original_error = original_error
        self.last_lines = last_lines

    def format(self):
        if self.lineno is None:
            return 'Syntax error: %s' % self.errmsg
        else:
            return 'Syntax error near line %d: %s' % (self.lineno, self.errmsg)


class BadSyntaxError(ValueError):
    """Error raised by subroutines when they cannot figure out what to do."""
    pass


class UnimplementedPoSyntaxError(NotImplementedError):
    """Exception for syntactical features we don't support."""
    pass


def consume_lines(nextline, input, startpattern, continuepattern):
    if startpattern.match(nextline) is None:
        raise ValueError('grrr')#BadSyntaxError
    lines = [nextline]
    for nextline in input:
        if continuepattern.match(nextline):
            lines.append(nextline)
        else:
            break
    else:
        nextline = None # EOF
    return nextline, lines


def extract_string(lines, header, continuationlength):
    line = lines[0]
    match = header.match(line)
    if not match:
        raise BadSyntaxError
    
    # get e.g. 'hello' from the line 'msgid "hello"', so skip 2 characters
    end = match.end()
    #assert line[end] == '"'
    headerline = line[end + 1:-2]
    
    # get 'hello' from line '"hello"'
    otherlines = [line[continuationlength:-2] for line in lines[1:]]
    return ''.join([headerline] + otherlines)

linepatternstrings = dict(comment=r'(#~ )?#[\s,\.:\|]|#~[,\.:\|]',
                          msgctxt=r'(#~ )?msgctxt ',
                          msgid=r'(#~ )?msgid ',
                          msgid_plural=r'(#~ )?msgid_plural ',
                          msgstr=r'(#~ )?msgstr ',
                          msgstr_plural=r'(#~ )?msgstr\[\d\] ',
                          continuation=r'(#~ )?"',
                          prevmsgid_start=r'#\| msgid ',
                          prevmsgid_continuation=r'#\| "')
linepatterns = dict([(key, re.compile(value))
                     for key, value in linepatternstrings.items()])
obsolete_linepatterns = dict([(key, re.compile(r'#~( ?)' + value))
                              for key, value in linepatternstrings.items()])


class PoParser:
    def __init__(self, input):
        self._input = input
        self.input = LineNumberIterator(input)
        self.last_chunk = None
        self.last_lines = []

    def get_message_chunks(self):
        input = self.input
        line = input.next()
        #self.last_lines.append(line)
        if len(self.last_lines) > 12:
            self.last_lines.pop()
        while True:
            msgdata = {}
            rawlines = []
            msgdata['rawlines'] = rawlines

            def _consume_lines(nextline, input, startpattern, continuepattern):
                try:
                    nextline, lines = consume_lines(nextline, input,
                                                    startpattern, 
                                                    continuepattern)
                except BadSyntaxError as error:
                    msg = 'Unrecognized syntax while parsing line %d' \
                        % input.lineno
                    newerror = PoError(msg,
                                       lineno=input.lineno,
                                       original_error=error,
                                       last_lines=input.last_lines)
                    raise newerror
                rawlines.extend(lines)
                return nextline, lines

            def _extract_string(nextline, input, header):
                nextline, lines = _consume_lines(nextline, input, header,
                                                 patterns['continuation'])
                continuationlength = 1
                if lines[-1].startswith('#~ "'):
                    continuationlength = 4
                string = extract_string(lines, header, continuationlength)
                return nextline, string
            
            patterns = linepatterns

            if patterns['comment'].match(line):
                line, comments = _consume_lines(line, input,
                                                patterns['comment'],
                                                patterns['comment'])
            else:
                comments = []

            if line.startswith('#~'):
                # Yuck!  Comments were not obsolete, but actual msgid was.
                is_obsolete = True
                patterns = obsolete_linepatterns
            else:
                is_obsolete = False

            # At least now we are sure whether it's really obsolete
            msgdata['is_obsolete'] = is_obsolete

            flags = []
            normalcomments = []
            for i, comment in enumerate(comments):
                if patterns['prevmsgid_start'].match(comment):
                    prevmsgid_lines = iter(comments[i + 1:])
                    _, lines = consume_lines(comment, prevmsgid_lines, 
                                             patterns['prevmsgid_start'],
                                             patterns['prevmsgid_continuation'])
                    prevmsgid = extract_string(lines, 
                                               patterns['prevmsgid_start'], 4)
                    msgdata['prevmsgid'] = prevmsgid
                if comment.startswith('#, '):
                    flags.extend(comment[3:].split(','))
                else:
                    normalcomments.append(comment)
            msgdata['comments'] = normalcomments
            msgdata['flags'] = [flag.strip() for flag in flags]

            if line.startswith('#~'): 
                # Aha!  It was an obsolete all along!
                # Must read all remaining lines as obsolete...
                is_obsolete = True
                patterns = obsolete_linepatterns

            if patterns['msgctxt'].match(line):
                line, msgctxt = _extract_string(line, input, patterns['msgctxt'])
                msgdata['msgctxt'] = msgctxt # XXX remember to take care of this

            if patterns['msgid'].match(line):
                line, msgid = _extract_string(line, input, patterns['msgid'])
                msgdata['msgid'] = msgid
                msgdata['lineno'] = input.lineno

            if patterns['msgid_plural'].match(line):#
                line, msgid_plural = _extract_string(line, input, 
                                                     patterns['msgid_plural'])
                msgdata['msgid_plural'] = msgid_plural

                nmsgstr = 0
                msgstrs = []
                pluralpattern = patterns['msgstr_plural']
                while line is not None and pluralpattern.match(line):
                    line, msgstr = _extract_string(line, input, 
                                                   pluralpattern)
                    msgstrs.append(msgstr)
                    nmsgstr += 1
                msgdata['msgstrs'] = msgstrs
            else:
                line, msgstr = _extract_string(line, input, patterns['msgstr'])
                msgdata['msgstrs'] = [msgstr]
            self.last_chunk = msgdata
            yield msgdata
            if line is None:
                return
        
    def chunk_iter(self, include_obsoletes=False):
        return self.get_message_chunks()

def parse(input):
    parser = PoParser(input)
    
    try:
        fname = input.name
    except AttributeError:
        fname = '<unknown>'

    chunks = []
    obsoletes = []

    chunk = None
    for chunk in parser.chunk_iter(include_obsoletes=True):
        if chunk['is_obsolete']:
            obsoletes.append(chunk)
        else:
            chunks.append(chunk)
    
    for chunk in chunks:
        if chunk['msgid'] == '':
            header = chunk
            break
    else:
        raise PoHeaderError('Header not found')

    for line in header['msgstrs'][0].split('\\n'):
        if line.startswith('Content-Type:'):
            break
    for token in line.split():
        if token.startswith('charset='):
            break
    encoding = token.split('=')[1]
    
    msgs = []
    for chunk in chunks + obsoletes:
        msgstrs = chunk['msgstrs']
        
        if len(msgstrs) > 1:
            assert 'msgid_plural' in chunk
        
        meta = dict(rawlines=[line.decode(encoding)
                              for line in chunk['rawlines']],
                    lineno=chunk['lineno'],
                    fname=fname,
                    encoding=encoding)
        
        if chunk['is_obsolete']:
            msgclass = ObsoleteMessage
        else:
            msgclass = Message

        def dec(txt):
            if isinstance(txt, basestring):
                return txt.decode(encoding)
            elif txt is None:
                return None
            else:
                return txt.decode(encoding)

        #print
        #print type(msgstr)
        #print repr(msgstr)
        #print msgstr
        #[dec(m) for m in msgstr]

        msg = msgclass(msgid=dec(chunk['msgid']),
                       msgstr=[dec(m) for m in msgstrs], # (includes plurals)
                       msgid_plural=dec(chunk.get('msgid_plural')),
                       msgctxt=dec(chunk.get('msgctxt')),
                       previous_msgid=dec(chunk.get('prevmsgid')),
                       comments=[dec(c) for c in chunk['comments']],
                       flags=[dec(f) for f in chunk['flags']],
                       meta=meta)
        msgs.append(msg)
        
    #obsoletes = [ObsoleteMessage(obsolete['comments'], 
    #                             meta=dict(encoding=encoding, fname=fname))
    #                             for obsolete in obsoletes]

    cat = Catalog(fname, encoding, msgs)
    return cat#.decode()


# XXX When parsing, allow stuff like:
# * allow for missing header
# * ignore encoding errors
# * ignoring bad syntax
