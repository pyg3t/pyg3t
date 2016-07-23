
from __future__ import print_function

from os import path, chdir
from subprocess import call

# Change to functionaltest dir for output
FUNCTIONALTESTDIR = path.dirname(path.abspath(__file__))
chdir(FUNCTIONALTESTDIR)

# Generate gtcat expected output
call('gtcat --encode ISO-8859-1 old.po|'
     'podiff -r - new.po > gtcat_expected_output',
     shell=True)

# Generate gtcheckargs expected output
call('gtcheckargs testpofile.da.po > gtcheckargs_expected_output', shell=True)

# Generate gtcompare expected output
call('gtcompare testpofile.da.po testpofile.da.po > '
     'gtcompare_expected_output', shell=True)

# Generate gtgrep expected output
call('gtgrep -i hello -s hej testpofile.da.po > gtgrep_expected_output',
     shell=True)

# Generate gtcompare expected output
call('gtmerge testpofile.da.po testpofile.da.po > '
     'gtmerge_expected_output', shell=True)

# Generate gtprevmsgdiff expected output
call('gtprevmsgdiff testpofile.da.po > gtprevmsgdiff_expected_output', shell=True)

# Generate gtwdiff expected output
call('gtwdiff testpodiff.podiff > gtwdiff_expected_output', shell=True)

# Generate gtxml expected output
call('gtxml testpofile.da.po > gtxml_expected_output', shell=True)

# Generate poabc expected output
call('poabc testpofile.da.po > poabc_expected_output', shell=True)

# Generate podiff expected output
call('podiff --relax old.po new.po > podiff_expected_output', shell=True)

# The popatch test is selfcontained, so no expected output for that

# Generate poselect expected output
call('poselect -ft testpofile.da.po > poselect_expected_output', shell=True)
