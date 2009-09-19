#!/usr/bin/env python
"""
gtparse -- A gettext parsing module in Python
Copyright (C) 2007-2009  Ask Hjorth Larsen <asklarsen@gmail.com>

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

import sys
import traceback
import codecs
import re
from optparse import OptionParser


version = '0.2'
        

class Entry:
    """This class represents a po-file entry. 

    Contains attributes that describe:

    * comments
    * msgid (possibly plural)
    * msgstr(s)
    * miscellaneous informations (line count, translation status)
    """

    def __init__(self):
        """Create an empty entry object.
        
        This will only initialize all the fields of an Entry object.
        Invoke the 'load' method to load information into it."""
        self.msgctxt = None
        self.msgid = None
        self.msgid_plural = None
        self.msgstr = None # This is ONLY the first, if there is more than one
        self.msgstrs = []
        self.hasplurals = False
        self.hascontext = False
        self.entryline = None # Line number of first comment
        self.linenumber = None # Line number of msgid
        self.rawlines = None # A list of the actual lines of this entry
        self.istranslated = False # Translated: not fuzzy, and no empty msgstr
        self.isfuzzy = False # Marked as fuzzy (having possibly empty msgstr)
        
    def load(self, lines, entryline=None):
        """Parse the lines of text, populating attributes of this object.

        Initializes the variables of this Entry according to the contents
        of the 'lines' parameter.  If entryline is specified, this will be
        stored as the line number of the entry in the po-file.

        Returns False if all lines are comments (such as for obsolete 
        entries), otherwise True."""
        self.entryline = entryline
        self.rawlines = tuple(lines)
        
        # Note: comment order has NOT been verified.
        comments = [line for line in lines if line.startswith('#')]
        self.comments = tuple(comments)
        commentcount = len(comments)

        if commentcount == len(lines):
            return False
        
        # Store the actual line number of the msgid
        self.linenumber = self.entryline + commentcount

        index = commentcount
        # Optional context
        self.hascontext = lines[commentcount].startswith('msgctxt ')
        if self.hascontext:
            self.msgctxt, index = extract_string('msgctxt ', lines, index)

        # Next thing should be the msgid
        self.msgid, index = extract_string('msgid ', lines, index)

        # Check for plural entries
        self.hasplurals = lines[index].startswith('msgid_plural ')
        if self.hasplurals:
            self.msgid_plural, index = extract_string('msgid_plural ',
                                                      lines, index)

            plurcount = 0
            while index < len(lines) and lines[index].startswith('msgstr['):
                string, index = extract_string('msgstr['+str(plurcount)+'] ',
                                               lines, index)
                plurcount += 1
                self.msgstrs.append(string)

            self.msgstr = self.msgstrs[0]

        else:
            self.msgstr, index = extract_string('msgstr ', lines, index)
            self.msgstrs = [self.msgstr]
        
        is_partially_translated = False
        for msgstr in self.msgstrs:
            if msgstr:
                is_partially_translated = True
                break
        
        if not is_partially_translated:
            self.istranslated = False
            self.isfuzzy = False
        else:
            fuzzy_flag_set = False
            for comment in self.getcomments('#, '):
                if comment.rfind('fuzzy') > 0:
                    fuzzy_flag_set = True
                    break
            #print fuzzy_flag_set
            self.istranslated = not fuzzy_flag_set
            self.isfuzzy = fuzzy_flag_set
        return True

    def getcomments(self, pattern='', strip=False):
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

    def tostring(self):
        return u''.join(self.rawlines)

    def copy(self):
        other = Entry()
        other.load(self.rawlines, self.entryline)
        return other


def extract_string(pattern, lines, index=0):
    """Extracts the text of an msgid or msgstr, not including 
    "msgid"/"msgstr", quotation marks or newlines.
    """
    # Rearrange indices
    lines = lines[index:]

    if not lines[0].startswith(pattern):
        raise Exception('Pattern "'+pattern+'" not found at start of string "'
                        + lines[0] + '".')


    lines[0] = lines[0][len(pattern):] # Strip pattern
    msglines = []
    for line in lines:
        if line.startswith('"'):
            msglines.append(line[1:-2]) # Strip quotation marks and newline
        else:
            break

    return ''.join(msglines), index + len(msglines)

def sortcomments(comments):
    """Get a tuple of lists of comments, each list being one comment type.

    Given a list of strings which must all start with '#', returns a tuple
    containing six lists of strings, namely the translator comments 
    ('# '), extracted comments ('#. '), references ('#: '), flags  ('#, ')
    and comments relating to previous strings ('#| ')."""
    raise DeprecationWarning('use Entry.getcomments(self, pattern, ...)')

    transl = []
    auto = []
    ref = []
    flag = []
    for comment in comments:
        if comment.startswith('#. '):
            auto.append(comment)
        elif comment.startswith('#: '):
            ref.append(comment)
        elif comment.startswith('#, '):
            flag.append(comment)
        elif comment.startswith('#  '):
            transl.append(comment)

    # Note: comment order has NOT been verified.
    return transl, auto, ref, flag

def grab_sub_string(string, pattern, terminator=None, start=0):
    """Extract sting enclosed by pattern and terminator.

    From the given string, returns the text enclosed within pattern and
    terminator (which is the start pattern unless otherwise specified).
    The return value is a tuple with the enclosed text, start index and end 
    index.
    """
    startindex = string.index(pattern) + len(pattern)
    if terminator is None:
        terminator = pattern
    endindex = string.index(terminator, startindex)
    
    return (string[startindex:endindex], startindex, endindex)


class LineNumberIterator:
    # XXX Can probably be replaced by using fileinput module
    def __init__(self, input):
        self.linenumber = 0
        self.input = input
    def next(self):
        line = self.input.next()
        self.linenumber += 1
        return line


class Parser:
    def read_entrylines(self, input):
        """Yield the lines corresponding to one entry, reading from input."""
        line = input.next()
        while line.isspace():
            line = input.next()
        while not line.isspace():
            yield line
            line = input.next()

    def read_entrylinesets(self, input):
        """Yield tuples (n, lines) of line number and lines forming entries."""
        lineiter = LineNumberIterator(input)
        while True:
            entrylines = list(self.read_entrylines(lineiter))
            if not entrylines:
                raise StopIteration
            lineno = lineiter.linenumber - len(entrylines)
            yield lineno, entrylines

    def parse(self, input, include_obsolete=False):
        """Yield all entries found in the input file."""
        for lineno, lines in self.read_entrylinesets(input):
            entry = Entry()
            if entry.load(lines, lineno) or include_obsolete:
                yield entry

    def parse_asciilike(self, input):
        """Like parse, but actively decode input as utf8."""
        return self.parse(codecs.iterdecode(input, 'utf8'))


class Printer:
    def __init__(self, out):
        self.out = out

    def w(self, string):
        print >> self.out, string,

    def write_entry(self, entry):
        self.write_comments(entry)
        if entry.hascontext:
            self.write_block('msgctxt', entry.msgctxt)
        self.write_block('msgid', entry.msgid)
        if entry.hasplurals:
            self.write_block('msgid_plural', entry.msgid_plural)
            for i, msgstr in enumerate(entry.msgstrs):
                self.write_block('msgstr[%d]' % i, msgstr)
        else:
            self.write_block('msgstr', entry.msgstr)
        self.write_terminator()

    def write_comments(self, entry):
        for comment in entry.comments:
            self.write_comment(comment)

    def write_comment(self, comment):
        self.w(comment)

    def write_block(self, identifier, string):
        self.w('%s "%s"\n' % (identifier, string))

    def write_terminator(self):
        self.w('\n')

