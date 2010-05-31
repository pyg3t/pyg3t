import sys
from optparse import OptionParser

from pyg3t import __version__
from pyg3t.gtparse import Parser


class Counter:
    def __init__(self, selector):
        self.name = selector.name
        self.selector = selector
        self.count = 0
        self.total = 0
    
    def evaluate(self, entry):
        result = self.selector.evaluate(entry)
        if result:
            self.count += 1
        self.total += 1
        return result


class NegatingSelector:
    def __init__(self, selector):
        self.selector = selector

    def evaluate(self, entry):
        return not self.selector.evaluate(entry)


class FuzzySelector:
    name = 'Fuzzy'
    def evaluate(self, entry):
        return entry.isfuzzy


class TranslatedSelector:
    name = 'Translated'
    def evaluate(self, entry):
        return entry.istranslated


class UntranslatedSelector:
    name = 'Untranslated'
    def evaluate(self, entry):
        return not entry.istranslated and not entry.isfuzzy


class PluralSelector:
    name = 'Plural'
    def evaluate(self, entry):
        return entry.hasplurals


class OrSelector:
    def __init__(self, selectors):
        self.name = 'or: %s' % list(selectors)
        self.selectors = selectors

    def evaluate(self, entry):
        for selector in self.selectors:
            if selector.evaluate(entry):
                return True
        return False

        
class AndSelector:
    def __init__(self, selectors):
        self.name = 'and: %s' % list(selectors)
        self.selectors = selectors
        
    def evaluate(self, entry):
        for selector in self.selectors:
            if not selector.evaluate(entry):
                return False
        return True


class PoSelect:
    def __init__(self, selector):
        self.selector = selector

    def select(self, entries):
        selector = self.selector
        for entry in entries:
            if entry.msgid and selector.evaluate(entry):
                yield entry


class EntryPrinter:
    def write(self, entry):
        print entry.tostring().encode('utf8')


class LineNumberEntryPrinter:
    def __init__(self, printer):
        self.printer = printer
    
    def write(self, entry):
        print 'Line %d' % entry.linenumber
        self.printer.write(entry)


def build_parser():
    usage = '%prog [OPTIONS] [FILE]'
    description = ('Select messages in po-file based on various criteria '
                   'and print selected messages to standard output.')
    parser = OptionParser(description=description, usage=usage,
                          version=__version__)
    parser.add_option('-t', '--translated', action='store_true',
                      help='select translated messages')
    parser.add_option('-u', '--untranslated', action='store_true',
                      help='select untranslated messages')
    parser.add_option('-f', '--fuzzy', action='store_true',
                      help='select fuzzy messages')
    parser.add_option('-p', '--plural', action='store_true',
                      help='select entries with plural forms')
    parser.add_option('-v', '--invert', action='store_true',
                      help='invert selection criterion')
    parser.add_option('-a', '--and', action='store_true', dest='and_',
                      help='require all, rather than any, selection criterion'
                      ' to trigger selection')
    parser.add_option('-n', '--line-number', action='store_true',
                      help='print line numbers of selected entries')
    parser.add_option('-s', '--summary', action='store_true',
                      help='print a summary when done')
    parser.add_option('-c', '--count', action='store_true',
                      help='suppress normal output; print a count of selected '
                      'entries')
    parser.add_option('-w', '--msgid-word-count', action='store_true',
                      help='suppress normal output; print the count of words '
                      'in the msgids of selected entries')
    parser.add_option('-l', '--msgid-letter-count', action='store_true',
                      help='suppress normal output; print the count of '
                      'letters in the msgids of selected entries')
    return parser


def main():
    p = build_parser()
    opts, args = p.parse_args()

    argc = len(args)
    if argc == 0:
        src = sys.stdin
    elif argc == 1:
        try:
            src = open(args[0])
        except IOError, err:
            p.error(err)
    else:
        p.error('Please specify either one file or no files.')

    selectors = []
    if opts.translated:
        selectors.append(TranslatedSelector())
    if opts.untranslated:
        selectors.append(UntranslatedSelector())
    if opts.fuzzy:
        selectors.append(FuzzySelector())
    if opts.plural:
        selectors.append(PluralSelector())
    
    selectors = [Counter(selector) for selector in selectors]
    
    if opts.and_:
        superselector = AndSelector(selectors)
    else:
        superselector = OrSelector(selectors)
    if opts.invert:
        superselector = NegatingSelector(superselector)
    
    counter = Counter(superselector)
    poselect = PoSelect(counter)
    
    parser = Parser()
    
    printer = EntryPrinter()
    if opts.line_number:
        printer = LineNumberEntryPrinter(printer)

    entries = parser.parse_asciilike(src)
    selected = poselect.select(entries)

    if opts.count:
        print len(list(selected))
    elif opts.msgid_letter_count:
        print sum([len(msg.msgid) for msg in selected])
    elif opts.msgid_word_count:
        print sum([len(msg.msgid.split()) for msg in selected])
    else:
        for entry in selected:
            printer.write(entry)

    
    if opts.summary:
        print 'Summary'
        print '-------'
        print '%16s %d' % ('Total analysed', counter.total)
        if len(selectors) > 1:
            print
        for selector in selectors:
            print '%16s %d' % (selector.name, selector.count)
        print
        if len(selectors) > 1:
            print '%16s %d' % ('Total found', counter.count)
