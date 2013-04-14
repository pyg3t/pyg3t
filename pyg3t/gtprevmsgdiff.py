import re
from difflib import SequenceMatcher
from optparse import OptionParser

from pyg3t.gtparse import parse, wrap
from pyg3t.util import Colorizer

#tokenizer = re.compile(r'\s+|\S+')
#tokenizer = re.compile(r'\\n|\w+|\W+')
tokenizer = re.compile(r'\w+|\W+')

class DefaultFormat:
    def insert(self, string):
        if string.endswith('\n'):
            return '<+%s+>\n' % string[:-1]
        return '<+%s+>' % string
    def delete(self, string):
        if string.endswith('\n'):
            return '<-%s->\n' % string[:-1]
        return '<-%s->' % string
    def replace(self, old, new):
        if new.endswith('\n'):
            return '<-%s|%s+>\n' % (old, new[:-1])
        return '<-%s|%s+>' % (old, new)
    def equal(self, string):
        return string

class FancyFormat:
    def __init__(self):
        self.oldcolor = Colorizer('old')
        self.newcolor = Colorizer('new')
        self.boringcolor = Colorizer('light blue')
    def insert(self, string):
        return self.newcolor.colorize(string)
    def delete(self, string):
        return self.oldcolor.colorize(string)
    def replace(self, old, new):
        return '%s%s' % (self.oldcolor.colorize(old), 
                         self.newcolor.colorize(new))
    def equal(self, string):
        return string#.replace('\\n', '\\n\n')#self.boringcolor.colorize(string)

def diff(old, new, formatter):
    oldwords = tokenizer.findall(old)
    newwords = tokenizer.findall(new)

    def isgarbage(string):
        return string.replace('\\n', '').isspace()
        #return string.isspace()

    differ = SequenceMatcher(isgarbage, a=oldwords, b=newwords)
    
    words = []
    for op, s1beg, s1end, s2beg, s2end in differ.get_opcodes():
        if op == 'equal':
            words.append(formatter.equal(''.join(oldwords[s1beg:s1end])))
        elif op == 'insert':
            words.append(formatter.insert(''.join(newwords[s2beg:s2end])))
        elif op == 'replace':
            oldchunk = ''.join(oldwords[s1beg:s1end])
            newchunk = ''.join(newwords[s2beg:s2end])
            words.append(formatter.replace(oldchunk, newchunk))
        elif op == 'delete':
            words.append(formatter.delete(''.join(oldwords[s1beg:s1end])))
    return ''.join(words)

def main():
    p = OptionParser()
    p.add_option('--fancy', action='store_true',
                 help='use colors to highlight changes')
    p.add_option('--include-translated', action='store_true',
                 help='write differences for translated messages as well')
    
    opts, args = p.parse_args()

    if opts.fancy:
        formatter = FancyFormat()
    else:
        formatter = DefaultFormat()
    
    assert len(args) == 1
    cat = parse(open(args[0]))
    for msg in cat:
        if not msg.has_previous_msgid:
            continue
        if msg.istranslated and not opts.include_translated:
            continue
        
        if msg.istranslated:
            status = 'translated'
        elif msg.isfuzzy:
            status = 'fuzzy'
        else:
            status = 'untranslated'
        
        header = 'Line %d (%s)' % (msg.meta['lineno'], status)
        print ('--- %s ' % header).ljust(78, '-')
        oldmsgid = msg.previous_msgid.replace('\\n', '\\n\n')
        newmsgid = msg.msgid.replace('\\n', '\\n\n')
        difference = diff(oldmsgid, newmsgid, formatter)
        print difference.rstrip('\n')
        #print repr(difference[-50:])
