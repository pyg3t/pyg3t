#!/usr/bin/env python

from __future__ import print_function
import sys
import xml.sax
from optparse import OptionParser

from pyg3t.gtparse import parse
from pyg3t.util import Colorizer, pyg3tmain, Encoder


class SuspiciousTagsError(ValueError):
    pass

class XMLElementSet(xml.sax.handler.ContentHandler):
    def __init__(self):
        xml.sax.handler.ContentHandler.__init__(self)
        self.elements = []

    def startElement(self, name, attrs):
        self.elements.append(name)

class GTXMLChecker:
    """XML parser class for checking bad xml in gettext translations.

    An msg is considered ill-formed if its msgid is valid xml while at
    least one msgstr is not.  Note that this is a heuristic; the msgid may
    happen to form valid xml by accident."""
    def __init__(self, compare_tags=False, known_tags=None):
        self.compare_tags = compare_tags
        if known_tags is None:
            known_tags = set()
        self.known_tags = set(known_tags)
    
    def _filter(self, string):
        # Surround the string with a root tag
        xml = u''.join([u'<xml>', string.replace(u'\\"', u'"'), u'</xml>'])
        return xml.encode('utf8')
    
    def parse_xml_elements(self, string):
        xmlstring = self._filter(string)
        elements = XMLElementSet()
        xml.sax.parseString(xmlstring, elements)
        # The first one will be <xml>...</xml> which we use to enclose all
        # strings, and should be ignored.  This is also why self.elements
        # can't (simply) be a set right away
        return set(elements.elements[1:])
    
    def check_msg(self, msg):
        """Raise SAXParseException if msg is considered ill-formed."""
        #encoding = msg.meta['encoding']
        msgid = msg.msgid
        if len(msgid) == 0:
            return True
        #if not '<' in msgid:
        #    return True
        try:
            msgid_elements = self.parse_xml_elements(msgid)
        except xml.sax.SAXParseException:
            return True # msgid is probably not supposed to be xml
        for msgstr in msg.msgstrs:
            msgstr_elements = self.parse_xml_elements(msgstr)

        if self.compare_tags:
            for tag in msgstr_elements:
                if not (tag in msgid_elements or tag in self.known_tags):
                    msg = u'Unrecognized element "%s" found in msgstr' % tag
                    raise SuspiciousTagsError(msg)

        return True
    
    def check_msgs(self, msgs):
        """Yield pairs (msg, errmsg) for msgs with ill-formed xml."""
        for msg in msgs:
            try:
                self.check_msg(msg)
            except (xml.sax.SAXParseException, SuspiciousTagsError), err:
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
                      help='write only whether each FILE passes or fails, '
                      'and the number of valid and invalid strings '
                      'for each file.')
    parser.add_option('-c', '--color', action='store_true',
                      help='highlight errors using color')
    parser.add_option('-f', '--fuzzy', action='store_true',
                      help='print warnings for fuzzy messages aside from '
                      'just translated messages.')
    parser.add_option('-t', '--tags', action='store_true',
                      help='print warnings when a translated message uses a '
                      'tag not found in the untranslated message')
    parser.add_option('--dump-tags', action='store_true',
                      help='write xml tags from untranslated messages to '
                      'stdout.  Suppress normal output.')
    parser.add_option('--tags-from', metavar='FILE',
                      help='print warnings about any tags not listed in FILE.'
                      '  FILE might contain output from --dump-tags.'
                      '  Implies --tags.')
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
    def __init__(self, out):
        self.out = out
    
    def get_header(self, filename, msg, err):
        return u'At line %d: %s' % (msg.meta['lineno'], err.args[0])
        
    def write_msg(self, msgstring, err):
        print(msgstring, file=self.out)

    def write(self, filename, msg, err):
        header = self.get_header(filename, msg, err)
        print(header, file=self.out)
        #print header.encode(msg.meta['encoding'])
        print(u'-' * min(78, len(header)), file=self.out)
        #print '-' * min(78, len(header))
        self.write_msg(msg.tostring(), err)


class MultiFileMsgPrinter(MsgPrinter):
    def get_header(self, filename, msg, err):
        if filename == '-':
            filename = '<stdin>'
        return u'%s, line %d: %s' % (filename, msg.meta['lineno'], 
                                     err.args[0])


class SilentMsgPrinter(MsgPrinter):
    def write(self, filename, msg, err):
        pass


class FileSummarizer:
    def __init__(self, out):
        self.out = out
    
    def write(self, filename, totalcount, badcount):
        if badcount:
            status = 'FAIL'
        else:
            status = 'OK'
        print(filename.rjust(40), file=self.out)
        print('%4d OK %2d bad: %s' % (totalcount, badcount, status),
              file=self.out)


class SilentFileSummarizer(FileSummarizer):
    def write(self, filename, totalcount, badcount):
        pass

colorizer = Colorizer('light red')
def colorize_errors(msg, err):
    #errmsg = str(err) # XXX use for something?
    #startpattern = '<unknown>:1:'
    #assert errmsg.startswith(startpattern)
    #charno = int(errmsg[len(startpattern):].split(':', 1)[0])
    charno = err.getColumnNumber() - len('<xml>')
    # XXX what about plurals
    for i, msgstr in enumerate(msg.msgstrs):
        color_start_index = max(charno - 3, 0)
        color_end_index = min(charno + 3, len(msgstr))
        part1 = msgstr[:color_start_index]
        part2 = msgstr[color_start_index:color_end_index]
        part3 = msgstr[color_end_index:]
        msgstr = ''.join([part1, colorizer.colorize(part2), part3])
        msg.msgstrs[i] = msgstr

@pyg3tmain
def main():
    parser = build_parser()
    opts, args = parser.parse_args()

    known_tags = []
    if opts.tags_from:
        known_tags = open(opts.tags_from).read().split()

    check_tags = opts.tags or opts.tags_from
    gtxml = GTXMLChecker(check_tags, known_tags)
    out = Encoder(sys.stdout, 'utf8') # overwritten below as necessary
    
    # Special mode to dump all tags and do nothing else
    if opts.dump_tags:
        tags = set()
        for filename, input in get_inputfiles(args, parser):
            cat = parse(input)
            out = Encoder(sys.stdout, cat.encoding)
            
            def addtags(string):
                try:
                    tags.update(gtxml.parse_xml_elements(string))
                except xml.sax.SAXParseException:
                    pass # don't add tags if msgid is not valid xml
            #encoding = cat.encoding
            for msg in cat:
                addtags(msg.msgid)
                if msg.hasplurals:
                    addtags(msg.msgid_plural)
        for tag in tags:
            print(tag, file=out)
        return

    color = opts.color

    if opts.summary:
        msgprinter = SilentMsgPrinter(out)
        fileprinter = FileSummarizer(out)
    else:
        if len(args) > 1:
            msgprinter = MultiFileMsgPrinter(out)
        else:
            msgprinter = MsgPrinter(out)
        fileprinter = SilentFileSummarizer(out)

    total_badcount = 0
    for filename, input in get_inputfiles(args, parser):
        cat = parse(input)
        if opts.fuzzy:
            cat = [msg for msg in cat # XXX not a catalog
                   if msg.istranslated or msg.isfuzzy]
        else:
            cat = [msg for msg in cat if msg.istranslated]
        badcount = 0
        for bad_msg, err in gtxml.check_msgs(cat):
            if color:
                colorize_errors(bad_msg, err)
            msgprinter.write(filename, bad_msg, err)
            badcount += 1
        fileprinter.write(filename, len(cat), badcount)
        total_badcount += badcount

    if opts.summary:
        print('-' * 78, file=out)
        print('Total errors', total_badcount, file=out)

    exitcode = int(total_badcount > 0)
    raise SystemExit(exitcode)
