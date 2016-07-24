from __future__ import print_function, unicode_literals
from optparse import OptionParser, OptionGroup

from pyg3t import __version__
from pyg3t.util import pyg3tmain, get_encoded_output, get_bytes_input
from pyg3t.gtparse import parse


class Counter:
    def __init__(self, selector):
        self.name = selector.name
        self.selector = selector
        self.count = 0
        self.total = 0

    def evaluate(self, msg):
        result = self.selector.evaluate(msg)
        if result:
            self.count += 1
        self.total += 1
        return result


class NegatingSelector:
    def __init__(self, selector):
        self.selector = selector

    def evaluate(self, msg):
        return not self.selector.evaluate(msg)


class FuzzySelector:
    name = 'Fuzzy'

    def evaluate(self, msg):
        return msg.isfuzzy


class TranslatedSelector:
    name = 'Translated'

    def evaluate(self, msg):
        return msg.istranslated


class UntranslatedSelector:
    name = 'Untranslated'

    def evaluate(self, msg):
        return not msg.istranslated and not msg.isfuzzy


class PluralSelector:
    name = 'Plural'

    def evaluate(self, msg):
        return msg.isplural


class OrSelector:
    def __init__(self, selectors):
        self.name = 'or: %s' % list(selectors)
        self.selectors = selectors

    def evaluate(self, msg):
        for selector in self.selectors:
            if selector.evaluate(msg):
                return True
        return False


class AndSelector:
    def __init__(self, selectors):
        self.name = 'and: %s' % list(selectors)
        self.selectors = selectors

    def evaluate(self, msg):
        for selector in self.selectors:
            if not selector.evaluate(msg):
                return False
        return True


class PoSelect:
    def __init__(self, selector):
        self.selector = selector

    def select(self, msgs):
        selector = self.selector
        for msg in msgs:
            if msg.msgid and selector.evaluate(msg):
                yield msg


#class MsgPrinter:
#    def __init__(self, fd):
#        self.fd = fd
#    def write(self, msg):
#        print >> self.fd, msg.tostring()


#class LineNumberMsgPrinter:
#    def __init__(self, printer):
#        self.printer = printer
#
#    def write(self, msg):
#        print 'Line %d' % msg.meta['lineno']
#        self.printer.write(msg)


def build_parser():
    usage = '%prog [OPTIONS] [FILE]'
    description = ('Select messages in po-file based on various criteria '
                   'and print selected messages to standard output.')
    parser = OptionParser(description=description, usage=usage,
                          version=__version__)

    selection = OptionGroup(parser, 'Selection options')
    output = OptionGroup(parser, 'Output options')

    selection.add_option('-t', '--translated', action='store_true',
                         help='select translated messages')
    selection.add_option('-u', '--untranslated', action='store_true',
                         help='select untranslated messages')
    selection.add_option('-f', '--fuzzy', action='store_true',
                         help='select fuzzy messages')
    selection.add_option('-p', '--plural', action='store_true',
                         help='select messages with plural forms')
    selection.add_option('-v', '--invert', action='store_true',
                         help='invert selection criterion')
    selection.add_option('-a', '--and', action='store_true', dest='and_',
                         help='require all, rather than any, selection '
                         'criterion to trigger selection')

    output.add_option('-n', '--line-number', action='store_true',
                      help='print line numbers of selected messages')
    output.add_option('-s', '--summary', action='store_true',
                      help='print a summary when done')
    output.add_option('-c', '--count', action='store_true',
                      help='suppress normal output; print a count of selected '
                      'messages')
    output.add_option('-w', '--msgid-word-count', action='store_true',
                      help='suppress normal output; print the count of words '
                      'in the msgids of selected messages')
    output.add_option('-l', '--msgid-letter-count', action='store_true',
                      help='suppress normal output; print the count of '
                      'letters in the msgids of selected messages')

    parser.add_option_group(selection)
    parser.add_option_group(output)

    return parser


@pyg3tmain(build_parser)
def main(p):
    opts, args = p.parse_args()

    if len(args) == 0:
        args = ['-']

    is_multifile = len(args) > 1

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

    for arg in args:
        fd = get_bytes_input(arg)
        fname = fd.name
        #printer = MsgPrinter(Encoder(sys.stdout, ))

        #if opts.line_number:
        #    printer = LineNumberMsgPrinter(printer)
        try:
            cat = parse(fd)
        except IOError as m:
            p.error(m)
        out = get_encoded_output(cat.encoding)
        selected = poselect.select(cat)

        def printcount(count):
            if is_multifile:
                print('%6d  %s' % (count, fname), file=out)
            else:
                print(count, file=out)

        if opts.count:
            printcount(len(list(selected)))
        elif opts.msgid_letter_count:
            printcount(sum([len(msg.msgid) for msg in selected]))
        elif opts.msgid_word_count:
            printcount(sum([len(msg.msgid.split()) for msg in selected]))
        else:
            for msg in selected:
                if opts.line_number:
                    print('Line %d' % msg.meta['lineno'], file=out)
                print(msg.tostring(), file=out)
                #printer.write(msg)

    if opts.summary:
        print(file=out)
        print('Summary', file=out)
        print('-------', file=out)
        print('%16s %d' % ('Total analysed', counter.total), file=out)
        if len(selectors) > 1:
            print(file=out)
        for selector in selectors:
            print('%16s %d' % (selector.name, selector.count), file=out)
        print(file=out)
        if len(selectors) > 1:
            print('%16s %d' % ('Total selected', counter.count), file=out)
