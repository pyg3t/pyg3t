#!/usr/bin/env python

import sys
import xml.sax
from optparse import OptionParser

from pyg3t import gtparse, __version__


class GTXMLChecker(xml.sax.handler.ContentHandler):
    """XML parser class for checking bad xml in gettext translations.

    An entry is considered ill-formed if its msgid is valid xml while at
    least one msgstr is not.  Note that this is a heuristic; the msgid may
    happen to form valid xml by accident."""
    def __init__(self):
        xml.sax.handler.ContentHandler.__init__(self)
    
    def _filter(self, string):
        # Surround the string with a root tag
        xml = u''.join([u'<xml>', string.replace(u'\\"', u'"'), u'</xml>'])
        return xml.encode('utf8')
    
    def check_string(self, string):
        xmlstring = self._filter(string)
        xml.sax.parseString(xmlstring, self)
        return True
    
    def check_entry(self, entry):
        """Raise SAXParseException if entry is considered ill-formed."""
        if not '<' in entry.msgid:
            return True
        try:
            self.check_string(entry.msgid)
        except xml.sax.SAXParseException:
            return True # msgid is probably not supposed to be xml
        for msgstr in entry.msgstrs:
            self.check_string(msgstr)
        return True
    
    def check_entries(self, entries):
        """Yield pairs (entry, errmsg) for entries with ill-formed xml."""
        for entry in entries:
            try:
                self.check_entry(entry)
            except xml.sax.SAXParseException, err:
                yield entry, err


def build_parser():
    usage = '%prog [OPTION]... [FILE]...'
    description = ('Parse the contents of each po-FILE, writing '
                   'warnings for entries suspected of containing ill-formed '
                   'xml.  A translated entry is considered ill-formed if '
                   'its msgid is well-formed xml while at least one of its '
                   'msgstrs is not.  If no FILE is given, '
                   'or if FILE is -, read from stdin.')
                   
    parser = OptionParser(usage=usage, description=description,
                          version=__version__)
    parser.add_option('-s', '--summary', action='store_true',
                      help=('write only whether each FILE passes or fails, '
                            'and the number of valid and invalid strings '
                            'for each file.'))
    parser.add_option('-f', '--fuzzy', action='store_true',
                      help=('print warnings for fuzzy entries aside from '
                            'just translated entries.'))
    return parser


def get_inputfiles(args, parser):
    """Yield file-like objects corresponding to the given list of filenames."""
    if len(args) == 0:
        yield sys.stdin
    
    for arg in args:
        if arg == '-':
            yield arg, sys.stdin
        else:
            try:
                input = open(arg, 'r')
            except IOError, err:
                parser.error(err)
            yield arg, input


class EntryPrinter:
    def get_header(self, filename, entry, err):
        return 'At line %d: %s' % (entry.linenumber, err)
        
    def write_entry(self, entrystring, err):
        print entrystring

    def write(self, filename, entry, err):
        header = self.get_header(filename, entry, err)
        print header
        print '-' * min(78, len(header))
        self.write_entry(entry.tostring().encode('utf8'), err)


class MultiFileEntryPrinter(EntryPrinter):
    def get_header(self, filename, entry, err):
        if filename == '-':
            filename = '<stdin>'
        return '%s, line %d: %s' % (filename, entry.linenumber, err)


class SilentEntryPrinter:
    def write(self, filename, entry, err):
        pass


class FileSummarizer:
    def write(self, filename, totalcount, badcount):
        if badcount:
            status = 'FAIL'
        else:
            status = 'OK'
        print filename.rjust(40),
        print '%4d OK %2d bad: %s' % (totalcount, badcount, status)


class SilentFileSummarizer:
    def write(self, filename, totalcount, badcount):
        pass


def main():
    parser = build_parser()
    opts, args = parser.parse_args()
    
    gtxml = GTXMLChecker()

    if opts.summary:
        entryprinter = SilentEntryPrinter()
        fileprinter = FileSummarizer()
    else:
        if len(args) > 1:
            entryprinter = MultiFileEntryPrinter()
        else:
            entryprinter = EntryPrinter()
        fileprinter = SilentFileSummarizer()

    total_badcount = 0
    for filename, input in get_inputfiles(args, parser):
        parser = gtparse.Parser()
        entries = parser.parse_asciilike(input)
        if opts.fuzzy:
            entries = [entry for entry in entries 
                       if entry.istranslated or entry.isfuzzy]
        else:
            entries = [entry for entry in entries if entry.istranslated]
        badcount = 0
        for bad_entry, err in gtxml.check_entries(entries):
            entryprinter.write(filename, bad_entry, err)
            badcount += 1
        fileprinter.write(filename, len(entries), badcount)
        total_badcount += badcount

    if opts.summary:
        print '-' * 78
        print 'Total errors', total_badcount


if __name__ == '__main__':
    main()
