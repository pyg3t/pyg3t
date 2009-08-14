from subprocess import Popen, PIPE
from StringIO import StringIO

from pyg3t.gtparse import Parser

text = open('testpofile.da.po').read()
proc = Popen('gtgrep &'.split(),
             stdin=PIPE, stdout=PIPE)
print >> proc.stdin, text
proc.stdin.close()
parser = Parser()
results = list(parser.parse(proc.stdout))
print results
assert len(results) == 1
assert results[0].msgid == 'Mail &daemon'
