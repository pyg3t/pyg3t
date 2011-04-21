#!/usr/bin/env python

import sys
import xml.sax
from optparse import OptionParser

from pyg3t.gtparse import parse


class GTXMLChecker(xml.sax.handler.ContentHandler):
    """XML parser class for checking bad xml in gettext translations.

    An msg is considered ill-formed if its msgid is valid xml while at
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
    
    def check_msg(self, msg):
        """Raise SAXParseException if msg is considered ill-formed."""
        encoding = msg.meta['encoding']
        msgid = msg.msgid.decode(encoding)
        if not '<' in msgid:
            return True
        try:
            self.check_string(msgid)
        except xml.sax.SAXParseException:
            return True # msgid is probably not supposed to be xml
        for msgstr in msg.msgstrs:
            self.check_string(msgstr.decode(encoding))
        return True
    
    def check_msgs(self, msgs):
        """Yield pairs (msg, errmsg) for msgs with ill-formed xml."""
        for msg in msgs:
            try:
                self.check_msg(msg)
            except xml.sax.SAXParseException, err:
                yield msg, err


def build_parser():
    usage = '%prog [OPTION]... [FILE]...'
    description = ('Parse the contents of each po-FILE, writing '
                   'warnings for messages suspected of containing ill-formed '
                   'xml.  A translated message is considered ill-formed if '
                   'its msgid is well-formed xml while at least one of its '
                   'msgstrs is not.  If no FILE is given, '
                   'or if FILE is -, read from stdin.')
                   
    parser = OptionParser(usage=usage, description=description)
    parser.add_option('-s', '--summary', action='store_true',
                      help=('write only whether each FILE passes or fails, '
                            'and the number of valid and invalid strings '
                            'for each file.'))
    parser.add_option('-f', '--fuzzy', action='store_true',
                      help=('print warnings for fuzzy messages aside from '
                            'just translated messages.'))
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


class MsgPrinter:
    def get_header(self, filename, msg, err):
        return 'At line %d: %s' % (msg.meta['lineno'], err)
        
    def write_msg(self, msgstring, err):
        print msgstring

    def write(self, filename, msg, err):
        header = self.get_header(filename, msg, err)
        print header
        print '-' * min(78, len(header))
        self.write_msg(msg.tostring(), err)


class MultiFileMsgPrinter(MsgPrinter):
    def get_header(self, filename, msg, err):
        if filename == '-':
            filename = '<stdin>'
        return '%s, line %d: %s' % (filename, msg.linenumber, err)


class SilentMsgPrinter:
    def write(self, filename, msg, err):
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
        msgprinter = SilentMsgPrinter()
        fileprinter = FileSummarizer()
    else:
        if len(args) > 1:
            msgprinter = MultiFileMsgPrinter()
        else:
            msgprinter = MsgPrinter()
        fileprinter = SilentFileSummarizer()

    total_badcount = 0
    for filename, input in get_inputfiles(args, parser):
        cat = parse(input)
        if opts.fuzzy:
            cat = [msg for msg in msgs # XXX not a catalog
                   if msg.istranslated or msg.isfuzzy]
        else:
            cat = [msg for msg in cat if msg.istranslated]
        badcount = 0
        for bad_msg, err in gtxml.check_msgs(cat):
            msgprinter.write(filename, bad_msg, err)
            badcount += 1
        fileprinter.write(filename, len(cat), badcount)
        total_badcount += badcount

    if opts.summary:
        print '-' * 78
        print 'Total errors', total_badcount


if __name__ == '__main__':
    main()
