#!/usr/bin/env python

"""Pretty-print or reformat po-files."""
# Note.  None of this actually works

from textwrap import TextWrapper
from optparse import OptionParser

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


# TextWrapper will normally remove initial and subsequent whitespace by
# deleting first and last chunks
class CustomTextWrapper(TextWrapper):
    def _wrap_chunks(self, chunks):
        chunks.append(' ')
        chunks.insert(0, ' ')
        TextWrapper._wrap_cunks(self, chunks)

class LineWrappingPrinter(Printer):
    def __init__(self, out, linewidth=78, preserve_msgid=True):
        self.linewith = linewidth
        self.contentwidth = linewidth - 2
        self.preserve_msgid = preserve_msgid
        self.wrapper = CustomTextWrapper()# XXX
        Printer.__init__(self, out)

    def format_lines_in_block(self, template, string):
        wrappedlines = textwrap.wrap(string, self.contentwidth)
        if len(lines) == 1:
            formattedstring = '%s "%%s"' % identifier
            if len(formattedstring) > self.linewidth:
                wrappedlines.insert(0, identifier + 0)
        #template % string
        # Not finished.....

    def write_block(self, identifier, string):
        physical_lines = iter(string.split('\\n'))
        if len(physical_lines) == 1:
            formattedstring = '%s "%s"' % (identifier, string)
            if len(formattedstring) > self.linewidth: # better make it shorter
                print >> self.out, '%s ""' % identifier
                for line in textwrap.wrap(string, self.contentwidth,
                                          #initial_indent='"',
                                          #subsequent_indent='"',
                                          expand_tabs=False,
                                          replace_whitespace=False,
                                          break_long_words=False):
                    print >> self.out, '"%s"' % string
            
        self.format_lines_in_block(starttemplate, physical_lines.next())
        
        #for physical_line in physical_lines:
        #    wrappedlines = textwrap.wrap(string, self.contentwidth)
        #    if len(lines) == 1:
        #        formattedstring = '%s "%%s"' % identifier
        #        if len(formattedstring) > self.linewidth:
        #            wrappedlines.insert(0, identifier + 

def main():
    usage = '%prog [OPTIONS] FILE'
    description = 'Pretty-print or reformat po-files.'
    parser = OptionParser(usage=usage)
    parser.add_option('-b', '--breaklines', action='store_true',
                      help='break long strings into multiple lines')
    parser.add_option('-w', '--width', type='int', default=80,
                      help='line width [default: %default]')

    opts, args = parser.parse_args()

if __name__ == '__main__':
    main()
