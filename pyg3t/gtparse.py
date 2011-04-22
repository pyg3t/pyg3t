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

import codecs
import re
from textwrap import TextWrapper

wordseparator = re.compile(r'(\s+)')

#wrapper = TextWrapper(width=77,
#                      replace_whitespace=False,
#                      expand_tabs=False,
#                      drop_whitespace=False)

# Built-in textwrapper doesn't support the drop_whitespace=False
# option before 2.6, and it's sort of nice to support 2.5 still.
# So this is sort of equivalent to the TextWrapper
class TextWrapper:
    def wrap(self, text):
        chunks = iter(wordseparator.split(text))
        lines = []
        tokens = []
        chars = 0
        for chunk in chunks:
            if chars + len(chunk) > 77:
                lines.append(''.join(tokens))
                tokens = []
                chars = 0
            if len(chunk) > 0:
                tokens.append(chunk)
                chars += len(chunk)
        if tokens:
            lines.append(''.join(tokens))
        return lines
wrapper = TextWrapper()




class Catalog(object):
    """A Catalog represents one gettext catalog, or po-file."""
    def __init__(self, fname, encoding, msgs, obsoletes=None):
        self.fname = fname
        self.encoding = encoding
        self.msgs = msgs
        if obsoletes is None:
            obsoletes = []
        self.obsoletes = obsoletes
        self.header = self._get_header()

    def _get_header(self):
        for msg in self.msgs:
            if msg.msgid == '':
                return msg
    
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

    # XXX todo implement this
    #def encode(self, encoding):
    #    for msg in self:
    #        ...
    #    cat = Catalog(self.fname, encoding) # XXX


class Message(object):
    """This class represents a po-file entry. 

    Contains attributes that describe:

    * comments
    * msgid (possibly plural)
    * msgstr(s)
    * miscellaneous informations (line count, translation status)"""

    def __init__(self, msgid, msgstr=None, msgid_plural=None,
                 msgctxt=None, comments=None, meta=None):
        """Create a Message, representing one message from a message catalog.
        
        All strings are assumed to be unicode.  XXX or are they?
        
        Parameters:
         * msgid: string
         * msgstr: string, or list of strings for plurals
         * msgid_plural: None, or a string if there are plurals
         * msgctxt: None, or a string if there is a message context
         * comments: list of newline-terminated strings (use [] if None)
         
         The two last arguments specify information that pertains to
         the file from which the message was loaded.  If the Message
         is not based on a file, these should be None.  rawlines is
         the original representation from an input file, if the
         original representation must be remembered.  lineno is the
         line number of the msgid in the file from which it was
         loaded.

         It is understood that the properties of a Message may be
         changed programmatically so as to render it inconsistent with
         its rawlines and/or lineno.
        """
        self.msgid = msgid
        self.msgid_plural = msgid_plural

        if msgid_plural is None:
            self.msgstr = msgstr
            self.msgstrs = [msgstr]
        else:
            # msgstr is a list; if it turns out to be a string, raise
            # an error to avoid confusion
            self.msgstr = msgstr[0]
            assert not isinstance(msgstr, basestring)
            self.msgstrs = msgstr
        
        if comments is None:
            comments = []
        self.comments = comments
        
        # The fuzzy flag is whether fuzzy is specified in the
        # comments.  It is ignored if the message has an empty
        # translation.
        self.fuzzyflag = False
        for comment in comments:
            if comment.startswith('#, ') and 'fuzzy' in comment:
                self.fuzzyflag = True
                break
        
        self.msgctxt = msgctxt
        
        # XXX TODO:
        # previous_msgid, has_previous_msgid
        self.previous_msgid = None
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
    def untranslated(self):
        return self.msgstr == ''

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

    def tostring(self):
        lines = []
        lines.extend(self.comments)
        if self.has_context:
            lines.append(wrap('msgctxt', self.msgctxt))
        lines.append(wrap('msgid', self.msgid))
        if self.hasplurals:
            lines.append(wrap('msgid_plural', self.msgid_plural))
            for i, msgstr in enumerate(self.msgstrs):
                lines.append(wrap('msgstr[%d]' % i, msgstr))
        else:
            lines.append(wrap('msgstr', self.msgstr))
        string = ''.join(lines)
        return string


class ObsoleteMessage(object):
    def __init__(self, comments, meta=None):
        self.comments = comments
        if meta is None:
            meta = {}
        self.meta = meta

    def tostring(self):
        return ''.join(self.comments)


def wrap(declaration, string):
    if len(string) + len(declaration) > 75 or '\\n' in string:
        tokens = []
        tokens.append('%s ""\n' % declaration)
        linetokens = string.split('\\n')
        for i, token in enumerate(linetokens[:-1]):
            linetokens[i] += '\\n' # grrr
        for linetoken in linetokens:
            lines = wrapper.wrap(linetoken)
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
    def pop_lines(self):
        lines = self.lines
        self.lines = []
        return lines
    def next(self):
        line = self.input.next()
        self.lineno += 1
        self.lines.append(line)
        return line


class PoSyntaxError(ValueError):
    pass


# Exception for cases we don't support, such as obsoletes (#~), future
# gettext features and so on
class UnimplementedPoSyntaxError(NotImplementedError):
    pass


def get_message_chunk(input):
    """Read text from input and yield a dictionary for each message.

    The format of this dictionary is subject to change."""
    msgdata = {}
    input.pop_lines()
    #assert len(input.pop_lines()) == 0
    
    line = input.next()
    while line.isspace():
        input.pop_lines()
        line = input.next()
    
    msgdata['lineno'] = input.lineno
    comments = []

    def extract_string(line, input, header):
        if not line.startswith(header + ' "'):
            raise PoSyntaxError('%s not found near line %d:\n%s'
                                % (header, input.lineno, 
                                   ''.join(input.pop_lines())))
        lines = []

        # get e.g. 'hello' from the line 'msgid "hello"'
        lines.append(line[len(header) + 2:-2])
        line = input.next()
        while line.startswith('"'):
            lines.append(line[1:-2]) # get 'hello' from line '"hello"'
            assert line.endswith('"\n'), line
            line = input.next()
        string = ''.join(lines)
        return line, string

    while line.startswith('#'):
        comments.append(line)
        line = input.next()
    msgdata['comments'] = comments

    if line.startswith('msgctxt "'):
        line, msgctxt = extract_string(line, input, 'msgctxt')
        msgdata['msgctxt'] = msgctxt # XXX remember to take care of this

    if not line.startswith('msgid "'):
        if any(previous_line.startswith('#~') 
               for previous_line in comments):
            msgdata['obsolete'] = True
            return msgdata

    line, msgid = extract_string(line, input, 'msgid')

    msgdata['msgid'] = msgid

    isplural = line.startswith('msgid_plural "')
    msgdata['isplural'] = isplural

    if isplural:
        line, msgid_plural = extract_string(line, input, 'msgid_plural')
        msgdata['msgid_plural'] = msgid_plural
        nmsgstr = 0
        msgstrs = []
        msgstr_token = 'msgstr[%d]' % nmsgstr
        while line.startswith(msgstr_token):
            line, msgstr = extract_string(line, input, msgstr_token)
            # XXXX what if chunk runs out of lines?
            
            msgstrs.append(msgstr)
            nmsgstr += 1
            msgstr_token = 'msgstr[%d]' % nmsgstr
        msgdata['msgstrs'] = msgstrs
    else:
        if not line.startswith('msgstr "'):
            raise PoSyntaxError('msgstr not found')
        line, msgstr = extract_string(line, input, 'msgstr')
        msgdata['msgstr'] = msgstr
    msgdata['rawlines'] = input.pop_lines()
    return msgdata

def chunk_iter(input, include_obsoletes=False):
    input = LineNumberIterator(input)
    while True:
        try:
            msgdata = get_message_chunk(input)
        except UnimplementedPoSyntaxError, e:
            pass
            #print e
        else:
            if not msgdata.get('obsolete') or include_obsoletes:
                yield msgdata


def parse(input):
    try:
        fname = input.name
    except AttributeError:
        fname = '<unknown>'

    chunks = []
    obsoletes = []
    
    for chunk in chunk_iter(input, include_obsoletes=True):
        if chunk.get('obsolete'):
            obsoletes.append(chunk)
        else:
            chunks.append(chunk)
    
    for chunk in chunks:
        if chunk['msgid'] == '':
            header = chunk
        break
    else:
        raise PoSyntaxError('Header not found')

    for line in header['msgstr'].split('\\n'):
        if line.startswith('Content-Type:'):
            break
    for token in line.split():
        if token.startswith('charset='):
            break
    encoding = token.split('=')[1]
    
    msgs = []
    for chunk in chunks:
        msgid = chunk['msgid']
        
        if 'msgstr' in chunk:
            assert not 'msgid_plural' in chunk
            msgstr = chunk['msgstr']
        elif 'msgid_plural' in chunk:
            msgstr = chunk['msgstrs']
        else:
            raise AssertionError('dictionary format acting up')
        
        comments = chunk['comments']
        rawlines = chunk['rawlines']

        meta = dict(rawlines=chunk['rawlines'],
                    lineno=chunk['lineno'],
                    fname=fname,
                    encoding=encoding)

        msgs.append(Message(msgid=chunk['msgid'],
                            msgstr=msgstr, # (includes any plurals)
                            msgid_plural=chunk.get('msgid_plural'),
                            msgctxt=chunk.get('msgctxt'),
                            comments=chunk['comments'],
                            meta=meta))
    
    obsoletes = [ObsoleteMessage(obsolete['comments'], 
                                 meta=dict(encoding=encoding, fname=fname))
                                 for obsolete in obsoletes]

    cat = Catalog(fname, encoding, msgs, obsoletes=obsoletes)
    return cat


# When parsing, allow stuff like:
# * allow for missing header
# * ignore encoding errors
# * ignoring bad syntax
