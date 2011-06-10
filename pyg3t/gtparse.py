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


def _get_header(msgs):
    for msg in msgs:
        if msg.msgid == '':
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
    
    def decode(self, encoding='utf8'):
        # XXX not really implemented
        msgs = [msg.decode(encoding) for msg in self]
        obsoletes = [obs.decode(encoding) for obs in self.obsoletes]
        cat = Catalog(self.fname, self.encoding, msgs, obsoletes)
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

    * comments
    * msgid (possibly plural)
    * msgstr(s)
    * miscellaneous informations (line count, translation status)"""

    is_obsolete = False

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

        # XXX right now the comments are always written as is, even if
        # someone changed the fuzzy flag programmatically.  We should
        # make it so the printed comments will be generated from the
        # programmed representation of the flags
        
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

    def __str__(self):
        return self.tostring()

class ObsoleteMessage(Message):
    
    is_obsolete = True

    def tostring(self):
        string = Message.tostring(self)
        lines = string.splitlines()
        # XXX does not re-wrap if line is too long
        return '\n'.join('#~ %s' % line for line in lines)
        
#   def __init__(self, comments, meta=None):
#        self.comments = comments
#        if meta is None:
#            meta = {}
#        self.meta = meta
#    def tostring(self):
#        return ''.join(self.comments)


def is_wrappable(declaration, string):
    if len(string) + len(declaration) > 75:
        return True
    newlineindex = string.find('\\n')
    
    # Don't wrap if newline is only at end of string
    if newlineindex > 0 and not newlineindex == len(string) - 2:
        return True
    return False

def wrap(declaration, string):
    if is_wrappable(declaration, string):
    #if len(string) + len(declaration) > 75 or '\\n' in string:
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
        self.iter = iter(self)
    
    def pop_lines(self):
        lines = self.lines
        self.lines = []
        return lines
    def __iter__(self):
        for line in self.input:
            self.lineno += 1
            if line.isspace():
                continue
            yield line
    def next(self):
        return self.iter.next()

class PoSyntaxError(ValueError):
    pass


# Exception for cases we don't support, such as obsoletes (#~), future
# gettext features and so on
class UnimplementedPoSyntaxError(NotImplementedError):
    pass


#def whole_chunk_iter(input):

def consume_lines(nextline, input, startpattern, continuepattern):
    if not nextline.startswith(startpattern):
        print 'pat=%s; line=%s' % (repr(startpattern), repr(nextline))
        lines = input.pop_lines()
        print 'lines'
        print '----'
        for line in lines:
            print line
        raise PoSyntaxError()#XXXX
    lines = [nextline]
    for nextline in input:
        if nextline.startswith(continuepattern):
            lines.append(nextline)
        else:
            break
    else:
        nextline = None # EOF
    return nextline, lines

def extract_string(lines, header):
    line = lines[0]
    if not line.startswith(header + ' "'):
        raise PoSyntaxError('%s not found.  Line was: %s' % (header, line))
    # get e.g. 'hello' from the line 'msgid "hello"'
    headerline = line[len(header) + 2:-2]
    
    # get 'hello' from line '"hello"'
    otherlines = [line[1:-2] for line in lines[1:]]
    return ''.join([headerline] + otherlines)

linepatterns = dict(comment='#',
                    msgctxt='msgctxt "',
                    msgid='msgid',
                    msgid_plural='msgid_plural',
                    msgstr='msgstr',
                    msgstr_plural='msgstr[%d]',
                    continuation='"')
obsolete_linepatterns = dict([(key, '#~ ' + value) 
                              for key, value in linepatterns.items()])

def get_message_chunks(input):
    input = LineNumberIterator(input)
    line = input.next()
    while True:
        msgdata = {}
        rawlines = []
        msgdata['rawlines'] = rawlines

        

        is_obsolete = line.startswith('#~ ')
        msgdata['is_obsolete'] = is_obsolete
        if is_obsolete:
            patterns = obsolete_linepatterns
        else:
            patterns = linepatterns
        
        def _consume_lines(nextline, input, startpattern, continuepattern):
            nextline, lines = consume_lines(nextline, input, startpattern, 
                                            continuepattern)
            rawlines.extend(lines)
            return nextline, lines
        def _extract_string(nextline, input, header):
            nextline, lines = _consume_lines(nextline, input, header,
                                             patterns['continuation'])
            string = extract_string(lines, header)
            return nextline, string

        if line.startswith(patterns['comment']):
            line, comments = _consume_lines(line, input, 
                                            patterns['comment'], 
                                            patterns['comment'])
        else:
            comments = []
        msgdata['comments'] = comments

        commenttypes = ['# ', '#. ', '#: ', '#, ', '#| msgid ']

        typed_comments = {}
        for key in commenttypes:
            typed_comments[key] = []

        for comment in comments:
            for key in commenttypes:
                if comment.startswith(key):
                    typed_comments[key].append(comment[len(key):])
        
        msgdata['typedcomments'] = typed_comments

        if line.startswith(patterns['msgctxt']):
            line, msgctxt = _extract_string(line, input, patterns['msgctxt'])
            msgdata['msgctxt'] = msgctxt # XXX remember to take care of this

        if line.startswith(patterns['msgid']):
            line, msgid = _extract_string(line, input, patterns['msgid'])
            msgdata['msgid'] = msgid
            msgdata['lineno'] = input.lineno
        #else:
        #    sdlkfjasdfkjasldfkjalfkjaslkdfjlkkj
        #    assert rawlines[-1].startswith('#~') # obsolete
        #    yield msgdata
        #    continue # XXXXXXX

        if line.startswith(patterns['msgid_plural']):
            line, msgid_plural = _extract_string(line, input, 
                                                 patterns['msgid_plural'])
            msgdata['msgid_plural'] = msgid_plural
            
            nmsgstr = 0
            msgstrs = []
            pluralpattern = patterns['msgstr_plural'] % nmsgstr
            while line.startswith(pluralpattern):
                line, msgstr = _extract_string(line, input, 
                                               pluralpattern)
                msgstrs.append(msgstr)
                nmsgstr += 1
                pluralpattern = patterns['msgstr_plural'] % nmsgstr
            msgdata['msgstrs'] = msgstrs
        else:
            line, msgstr = _extract_string(line, input, patterns['msgstr'])
            msgdata['msgstr'] = msgstr
        yield msgdata
        if line is None:
            return

# XXX lineno should be input.lineno + len(comments)

        
def chunk_iter(input, include_obsoletes=False):
    return get_message_chunks(input)

def parse(input):
    try:
        fname = input.name
    except AttributeError:
        fname = '<unknown>'

    chunks = []
    obsoletes = []
    
    for chunk in chunk_iter(input, include_obsoletes=True):
        if chunk['is_obsolete']:
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
    for chunk in chunks + obsoletes:
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
        
        if chunk['is_obsolete']:
            msgclass = ObsoleteMessage
        else:
            msgclass = Message

        msgs.append(msgclass(msgid=chunk['msgid'],
                             msgstr=msgstr, # (includes any plurals)
                             msgid_plural=chunk.get('msgid_plural'),
                             msgctxt=chunk.get('msgctxt'),
                             comments=chunk['comments'],
                             meta=meta))
        
    #obsoletes = [ObsoleteMessage(obsolete['comments'], 
    #                             meta=dict(encoding=encoding, fname=fname))
    #                             for obsolete in obsoletes]

    cat = Catalog(fname, encoding, msgs)
    return cat


# XXX When parsing, allow stuff like:
# * allow for missing header
# * ignore encoding errors
# * ignoring bad syntax
