#from subprocess import Popen, PIPE
from optparse import OptionGroup

"""
class MsgcatPrinter(BasePrinter):
    def __init__(self, printer):
        self.printer = printer
        self.msgcat = Popen(['msgcat'], stdin=PIPE)
        
    def print_entry(self, entry):
        self.printer.print_entry(entry)
"""        

class BasePrinter:
    def __init__(self, fd):
        self.fd = fd
    
    def print_entries(self, entries):
        for entry in entries:
            self.print_entry(entry)
            print >> self.fd

    def print_entry(self, entry):
        raise NotImplementedError


class SimplePrinter(BasePrinter):
    def print_entry(self, entry):
        for line in entry.rawlines:
            print >> self.fd, line


class CleanPrinter(BasePrinter):
    def print_entry(self, entry):
        fd = self.fd
        for comment in entry.get_comments():
            print >> fd, comment
        print >> fd, 'msgid "%s"' % entry.msgid
        if entry.hasplurals:
            print >> fd, 'msgid_plural "%s"' % entry.msgid_plural
            for i, msgstr in enumerate(entry.msgstrs):
                print >> fd, 'msgstr[%d] "%s"' % (i, msgstr)
        else:
            print >> fd, 'msgstr "%s"' % entry.msgstr
