#!/usr/bin/python
"""
gtparse -- A gettext parsing module in Python
Copyright (C) 2007-2008  Ask Hjorth Larsen <asklarsen@gmail.com>

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
from optparse import OptionParser

class EntrySet:
    """This class represents a list of Entries, and exposes methods for
    managing statistics."""
    def __init__(self, entries, obsoletes=()):
        """Creates a new EntrySet from the provided list of entries."""
        self.entries = list(entries)
        self.obsoletes = list(obsoletes)
        self.__stats__ = None

    def get(self, propertyname):
        """Given a string which is the name of a field of the Entry class,
        returns the list of values of this field for all entries."""
        return [getattr(entry,propertyname) for entry in self.entries]

    def getfuzzy(self):
        """Returns a new EntrySet consisting of all fuzzy Entries."""
        return EntrySet([entry for entry in self.entries
                         if entry.isfuzzy])

    def gettranslated(self):
        """Returns a new EntrySet consisting of all translated Entries."""
        return EntrySet([entry for entry in self.entries
                         if entry.istranslated])

    def getuntranslated(self):
        """Returns a new EntrySet consisting of all untranslated Entries."""
        return EntrySet([entry for entry in self.entries
                         if not entry.isfuzzy and not entry.istranslated])

    def getobsolete(self):
        return EntrySet([], self.obsoletes)

    def stats(self):
        """Returns a lazily-initialized Stats-object for this EntrySet."""
        if self.__stats__ == None:
            self.__stats__ = Stats(self.entries)
        return self.__stats__


class PoFile(EntrySet):
    """Represents a po-file. Contains a list of entries plus some high-level
    information pertaining to the header."""
    def __init__(self, lines):
        """Initializes this PoFile from the provided list of lines."""
        entries, obsoletes = parselines(lines)
        EntrySet.__init__(self, entries, obsoletes)
        header = self.entries[0]
        self.headercomments = header.getcomments('# ')
        props = {}
        self.headerproperties = props

        for line in header.msgstr.split('\\n'):
            kv = line.split(':')
            if len(kv) == 2:
                props[kv[0].strip()] = kv[1].strip()

        self.name = props.get('Project-Id-Version')
        self.lasttranslator = props.get('Last-Translator')

class Stats:
    """Class for managing statistics for a list of Entries."""
    def __init__(self, entries):
        """Initializes a number of fields with various statistical
        information about the given list of Entries"""
        fuzzy = untranslated = total = translated = pluralentries = 0
        msgid_chars = msgstr_chars = 0
        msgid_words = msgstr_words = 0
        
        for entry in entries[1:]:
            total += 1
            if entry.istranslated:
                translated += 1
            elif entry.isfuzzy:
                fuzzy += 1
            else:
                untranslated += 1

            msgid_chars += len(entry.msgid)
            msgid_words += len(entry.msgid.split())
            if entry.hasplurals:
                msgid_chars += len(entry.msgid_plural)
                msgid_words += len(entry.msgid_plural.split())
                msgstr_chars += sum([len(string) for string in entry.msgstrs])
                msgstr_words += sum([len(string.split()) for string
                                     in entry.msgstrs])
                pluralentries += 1
            else:
                msgstr_chars += len(entry.msgstr)
                msgstr_words += len(entry.msgstr.split())

        self.fuzzy = fuzzy
        self.untranslated = untranslated
        self.total = total
        self.pluralentries = pluralentries
        self.translated = translated

        self.msgid_chars = msgid_chars
        self.msgstr_chars = msgstr_chars
        self.msgid_words = msgid_words
        self.msgstr_words = msgstr_words

        self.avg_msgid_chars = msgid_chars / total
        self.avg_msgstr_chars = msgstr_chars / total

    def __str__(self):
        keyvalstrings = [''.join([key, ': ', str(val),'\n'])
                         for key, val in self.__dict__.items()]
        keyvalstrings.sort()
        return ''.join(keyvalstrings)
        

class Entry:
    """This class represents a po-file entry. Contains fields that describe:

    * comments (translator-, automatic, reference and flag types)
    * msgid
    * msgstr(s)
    * miscellaneous informations (line count, translation status)
    """

    def __init__(self):
        """This will only initialize all the fields of an Entry object.
        Invoke the 'load' method to load information into it."""
        #self.translatorcomments = [] # Comments starting with '# '
        #self.extractedcomments = [] # Comments starting with '#. '
        #self.references = [] # Comments starting with '#
        #self.flag = []
        self.msgctxt = None
        self.msgid = None
        self.msgid_plural = None
        self.msgstr = None # This is ONLY the first, if there is more than one
        self.msgstrs = []
        self.hasplurals = False
        self.hascontext = False
        self.entryline = None # Line number of first comment
        self.linenumber = None # Line number of msgid
        self.rawlines = [] # A list of the actual lines of this entry
        self.istranslated = False # Translated: not fuzzy, and no empty msgstr
        self.isfuzzy = False # Marked as fuzzy (having possibly empty msgstr)
        
    def load(self, lines, entryline=None):
        """Initializes the variables of this Entry according to the contents
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

        self.isfuzzy = False
        for comment in self.getcomments('#, '):
            if comment.rfind('fuzzy') > 0:
                # There might be trouble with strings that are not translated,
                # but marked as fuzzy nonetheless.
                self.isfuzzy = True

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


        self.istranslated = (not self.isfuzzy) and \
                            (self.msgstrs.count('') == 0)

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


    def __str__(self):
        return ''.join(self.rawlines)

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
    """Given a list of strings which must all start with '#', returns a tuple
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
        elif comment.startswith('#~ '):
            raise Exception('Antiquated comment '+comment)
        elif comment.startswith('#  '):
            transl.append(comment)            

    # Note: comment order has NOT been verified.
    return transl, auto, ref, flag

def grab_sub_string(string, pattern, terminator=None, start=0):
    """From the given string, returns the text enclosed within pattern and
    terminator (which is the start pattern unless otherwise specified).
    The return value is a tuple with the enclosed text, start index and end 
    index.
    """
    startindex = string.index(pattern) + len(pattern)
    if terminator is None:
        terminator = pattern
    endindex = string.index(terminator, startindex)
    
    return (string[startindex:endindex], startindex, endindex)


def loadfile(name):
    """Returns a PoFile-object corresponding to the supplied filename."""
    input = open(name)
    pofile = PoFile()
    pofile.load(input)
    return pofile


def parselines(lines):
    """Parses the supplied list of lines, returning a list of Entry-objects."""
    # The plan is to find the empty lines, then make one entry
    # for each chunk between two empty lines.
    # First, however, make sure the file is nice and tidy
    if not lines[-1].endswith('\n'):
        lines[-1] = lines[-1] + '\n'
    if lines[-1] != '\n':
        lines.append('\n')

    whitespacelines = [lnum for lnum, line in enumerate(lines)
                       if line == '\n']
    
    start = 0
    entrychunks = []
    for end in whitespacelines:
        entrychunks.append(lines[start:end])
        start = end + 1
        
    entries = []
    obsoletes = []
    
    # Note: prepend [0] as a white-space line, since this would
    # logically be  white space by continuation (sorry)
    for whitelinenum, chunk in zip([0]+whitespacelines, entrychunks):
        linecount = whitelinenum + 1
        try:
            entry = Entry()
            successful = entry.load(chunk, linecount)
            if successful:
                entries.append(entry)
            else:
                obsoletes.append(entry)
        except:
            traceback.print_exc()
            sys.exit()

    return entries, obsoletes


def colorize(string, id):
    if id is None:
        return string
    return '\x1b[%sm%s\x1b[0m' % (id, string)


class Printer:
    def __init__(self, out):
        self.out = out
        self.w = out.write

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

col = {'blue': '0;34', 'light red': '1;31', 'light purple': '1;35', 
       'brown': '0;33', 'purple': '0;35', 'yellow': '1;33', 
       'dark gray': '1;30', 'light cyan': '1;36', 'black': '0;30', 
       'light green': '1;32', 'cyan': '0;36', 'green': '0;32', 
       'light blue': '1;34', 'light gray': '0;37', 'white': '1;37', 
       'red': '0;31', None: None}


class Scheme:
    def __init__(self, type, msg, comment_id, comment, notice):
        self.type = col[type]
        self.msg = col[msg]
        self.comment_id = col[comment_id]
        self.comment = col[comment]
        self.notice = col[notice]


schemes = {'greenish' : Scheme('green', 'light blue', 'light cyan', 'cyan', 
                          'yellow'),
           'simple' : Scheme(None, 'red', None, 'blue',
                           'green')}


class PrettyPrinter(Printer):
    def __init__(self, out, scheme):
        Printer.__init__(self, out)
        self.scheme = scheme

    def write_comment(self, comment):
        scheme = self.scheme
        c1, c2 = scheme.comment_id, scheme.comment
        if comment.startswith('#, ') and comment.find('fuzzy') > 0:
            c2 = scheme.notice
        self.w(colorize(comment[:2], c1) + 
               colorize(comment[2:], c2))

    def write_block(self, identifier, string):
        scheme = self.scheme
        secondary = scheme.type
        if string == '':
            secondary = scheme.notice
        identifier = colorize(identifier, secondary)
        if string == 'msgctxt ':
            primary = scheme.notice
        else:
            primary = scheme.msg
        string = colorize(string, scheme.msg)
        quote = colorize('"', secondary)
        self.w('%s %s%s%s\n' % (identifier, quote, string, quote))

def main():
    """Method for testing things."""
    parser = OptionParser()
    parser.add_option('-c', '--color', help='Print fancy colors',
                      action='store_true')
    parser.add_option('-s','--color-scheme',
                      help='Color scheme to use.',
                      dest='scheme', default='simple')
    parser.add_option('-p', '--pipe', action='store_true',
                      help='Read from standard input')
    parser.add_option('-x', '--exclude-obsolete', action='store_true',
                      dest='exclude_obsolete',
                      help='Exclude obsolete entries from output')

    opts, args = parser.parse_args()

    # to do: write options
    argc = len(args)
    if argc > 1:
        print 'One file at a time!'
        sys.exit(0)
    elif argc == 0:
        if opts.pipe:
            source = sys.stdin
        else:
            filename = 'gwenview.po'#'seahorse.gnome-2-18.da.po'
            source = codecs.open(filename, 'utf-8')
    else:
        source = open(args[0])
    lines = source.readlines()
    pofile = PoFile(lines)
    if opts.color:
        p = PrettyPrinter(sys.stdout, schemes[opts.scheme])
    else:
        p = Printer(sys.stdout)
    for entry in pofile.entries:
        p.write_entry(entry)
    if not opts.exclude_obsolete:
        for entry in pofile.obsoletes:
            p.write_comments(entry)
            p.write_terminator()

    #print pofile.entries[-1]
    return pofile

if __name__ == '__main__':
    main()
