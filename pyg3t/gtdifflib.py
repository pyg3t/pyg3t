from __future__ import print_function, unicode_literals
from difflib import SequenceMatcher
from pyg3t.util import ansi, regex

#tokenizer = regex(r'\s+|\S+')
#tokenizer = regex(r'\\n|\w+|\W+')
tokenizer = regex(r'\w+|\W+')


class DefaultWDiffFormat:
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


class FancyWDiffFormat:
    def __init__(self):
        self.oldcolor = ansi.old
        self.newcolor = ansi.new
        self.boringcolor = ansi.light_blue

    def insert(self, string):
        return self.newcolor(string)

    def delete(self, string):
        return self.oldcolor(string)

    def replace(self, old, new):
        return '%s%s' % (self.oldcolor(old),
                         self.newcolor(new))

    def equal(self, string):
        return string


def diff(old, new, formatter):
    # XXXXXXXXXXXXXXXXX replace with appropriate split
    oldwords = tokenizer.findall(old)
    newwords = tokenizer.findall(new)

    def isgarbage(string):
        return string.replace('\\n', '').isspace()

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
