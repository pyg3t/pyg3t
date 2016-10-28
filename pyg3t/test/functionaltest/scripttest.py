#!/usr/bin/env python
from __future__ import print_function
from subprocess import Popen, PIPE
import sys

# This test mostly checks that the scripts run.
#
# The test passes if it prints nothing to stderr.


out = open('output.txt', 'w')

pycmd = 'python3' if sys.version_info[0] == 3 else 'python2'

print('pyg3t small script test suite')
print('Interpreter: %s' % sys.version)
print()
print('Testing')
print('-------')

def py(cmd):
    return '%s ../../../bin/%s' % (pycmd, cmd)

scripts = {}
for name in ['gtcat', 'gtcheckargs', 'gtcompare', 'gtgrep', 'gtmerge',
             'gtprevmsgdiff', 'gtwdiff', 'gtxml', 'poabc', 'podiff',
             'popatch', 'poselect']:
    scripts[name] = py(name)

othervars = {'file': 'testpofile.da.po',
             'out': 'output.txt',
             'diff1': 'old.po',
             'diff2': 'new.po'}

substitutions = {}
substitutions.update(scripts)
substitutions.update(othervars)

def run(cmd):
    proc = Popen(cmd % substitutions, shell=True)
    status = proc.wait()
    return status

print('gtcat')
run('%(gtcat)s --encode ISO-8859-1 old.po| %(podiff)s -r - new.po > /dev/null')

print('gtcheckargs')
run('%(gtcheckargs)s %(file)s >> %(out)s')

print('gtcompare')
run('%(gtcompare)s %(file)s %(file)s >> %(out)s')

print('gtgrep')
run('%(gtgrep)s -i hello -s hej %(file)s >> %(out)s')

print('gtmerge')
run('%(gtgrep)s %(file)s %(file)s >> %(out)s')

print('gtprevmsgdiff')
run('%(gtprevmsgdiff)s %(file)s >> %(out)s')

print('gtwdiff')
run('%(gtwdiff)s testpodiff.podiff >> %(out)s')

print('gtxml')
run('%(gtxml)s %(file)s >> %(out)s')
run('%(gtxml)s --color %(file)s >> %(out)s')

print('poabc')
run('%(poabc)s %(file)s >> %(out)s')

print('podiff')
run('%(podiff)s --relax %(diff1)s %(diff2)s >> %(out)s')
# Podiff test for files with different encodings

print('popatch')
run('%(popatch)s %(file)s testpodiff.podiff > patched.po '
    '&& %(gtcat)s patched.po > /dev/null')
run('%(popatch)s --new testpodiff.podiff > patched.new.po')
run('%(popatch)s --old testpodiff.podiff > patched.old.po')
run('%(podiff)s -rf patched.old.po patched.new.po > patched.diffed.podiff')
# patched.diffed.podiff should now be identical to the original diff
# ....except line numbers.

print('poselect')
run('%(poselect)s -ft %(file)s >> %(out)s')
