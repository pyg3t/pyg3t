# encoding: utf-8

"""This module performs functional tests of the pyg3t tools."""


import subprocess
import os


CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
FILE='testpofile.da.po'


def prepend_path(filepath):
    """Return the absolute path of a file in the functionaltest folder"""
    return os.path.join(CURRENT_DIR, filepath)


def run_command(command_args):
    """Run a command

    Args:
        command_args (list): List of command and arguments e.g. ['ls', '-l']

    Returns:
        tuple: (return_code (int), stdout (str), stderr (str)) 
    """
    process = subprocess.Popen(command_args,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                cwd=CURRENT_DIR)
    stdout, stderr = process.communicate()
    process.wait()
    return process.returncode, stdout, stderr


def standardtest(command_args, expected, return_code=0):
    """Perform the standard tests on a command.

    The standard tests consist of making sure that the return_code is as
    expected, that stderr is empty and that stdout has the expected value.
    """
    return_code_actual, stdout, stderr = run_command(command_args)
    assert return_code_actual == return_code
    assert stderr == ''
    assert stdout == expected


def test_gtcat():
    """Functional test for gtcat

    This test uses the old.po, new.po and gtcat_expected_output files.
    """
    # Complete command:
    # gtcat --encode ISO-8859-1 old.po|podiff -r - new.po
    process1 = subprocess.Popen(
        ['gtcat', '--encode', 'ISO-8859-1', 'old.po'],
        stdout=subprocess.PIPE, cwd=CURRENT_DIR
    )
    process2 = subprocess.Popen(
        ['podiff', '-r', '-', 'new.po'], stdin=process1.stdout,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=CURRENT_DIR
    )
    # Forward output
    process1.stdout.close()
    # Wait for process to close and set return code and check it
    process1.wait()
    assert process1.returncode == 0

    # Get final stdout and stderr
    stdout, stderr = process2.communicate()
    # Check return code
    process2.wait()
    assert process2.returncode == 0
    # Check stderr and stdout
    assert stderr == ''
    with open(prepend_path('gtcat_expected_output')) as file_:
        expected = file_.read()
        assert stdout == expected


def test_gtcheckargs():
    """Functional test for gtcheckargs"""
    expected = ''\
        'Line 149: Different number of options/vars or bad separators\n'\
        '------------------------------------------------------------\n'\
        '# Command line options with faulty translation\n'\
        'msgid "  -c, --coffee=AMOUNT    Make AMOUNT of coffee"\n'\
        'msgstr "      --coffee=MÆNGDE    Lav MÆNGDE kaffe"\n\n'\
        'Found 1 error.\n'
    standardtest(['gtcheckargs', FILE], expected, return_code=1)


def test_gtcompare():
    """Functional test for gtcompare"""
    expected = ''\
        'Template creation dates coincide\n'\
        'Translation revision dates coincide\n'\
        '\n'\
        'Each file contains 20 msgids, and they are all identical.\n'\
        '\n'\
        '5 messages remain untranslated.\n'\
        '0 untranslated messages changed to fuzzy.\n'\
        '0 untranslated messages changed to translated.\n'\
        '0 fuzzy messages changed to untranslated.\n'\
        '2 messages remain fuzzy.\n'\
        '0 fuzzy messages changed to translated.\n'\
        '0 translated messages changed to untranslated.\n'\
        '0 translated messages changed to fuzzy.\n'\
        '13 messages remain translated.\n'\
        '\n'\
        'There are no conflicts among translated messages.\n'
    standardtest(['gtcompare', FILE, FILE], expected)


def test_gtgrep():
    """functional test for gtgrep"""
    expected = ''\
        '# Translated string\n'\
        '#: helloworld.c:42\n'\
        'msgid "Hello world!"\n'\
        'msgstr "Hej verden!"\n\n'
    standardtest(['gtgrep', '-i', 'hello', '-s', 'hej', FILE], expected)


def test_gtmerge():
    """Functional test for gtmerge"""
    with open(prepend_path('gtmerge_expected_output')) as file_:
        expected = file_.read()
    standardtest(['gtmerge', FILE, FILE], expected)


def test_gtprevmsgdiff():
    """Functional test for gtprevmsgdiff"""
    expected = ''\
        '--- Line 47 (untranslated) --------------------------------------'\
        '-------------\n'\
        'How many <-software translators|French people+> does it take to '\
        'change a light bulb?\n'
    standardtest(['gtprevmsgdiff', FILE], expected)


def test_gtwdiff():
    """Functional test for gtwdiff"""
    with open(prepend_path('gtwdiff_expected_output')) as file_:
        expected = file_.read()
    standardtest(['gtwdiff', 'testpodiff.podiff'], expected)


def test_gtxml():
    """Functional test for gtxml"""
    with open(prepend_path('gtxml_expected_output')) as file_:
        expected = file_.read()
    standardtest(['gtxml', FILE], expected, return_code=1)

def test_poabc():
    """Functional test for poabc"""
    with open(prepend_path('poabc_expected_output')) as file_:
        expected = file_.read()
    standardtest(['poabc', FILE], expected)


def test_podiff():
    """Functional test for podiff"""
    with open(prepend_path('podiff_expected_output')) as file_:
        expected = file_.read()
    standardtest(['podiff', '--relax', 'old.po', 'new.po'], expected)


def test_popatch():
    """Functional test for popatch"""
    return_code, stdout, stderr = run_command(
        ['popatch', 'testpofile.da.po', 'testpodiff.podiff'])
    assert return_code == 0
    assert stderr == ''
    with open(prepend_path('patched.po'), 'w') as file_:
        file_.write(stdout)

    return_code, stdout, stderr = run_command(
        ['popatch', '--new', 'testpodiff.podiff'])
    assert return_code == 0
    assert stderr == ''
    with open(prepend_path('patched.new.po'), 'w') as file_:
        file_.write(stdout)

    return_code, stdout, stderr = run_command(
        ['popatch', '--old', 'testpodiff.podiff'])
    assert return_code == 0
    assert stderr == ''
    with open(prepend_path('patched.old.po'), 'w') as file_:
        file_.write(stdout)

    return_code, stdout, stderr = run_command(
        ['podiff', '-rf', 'patched.old.po', 'patched.new.po'])
    assert return_code == 0
    assert stderr == ''
    with open(prepend_path('testpodiff.podiff')) as file_:
        lines_diff = file_.readlines()
    for line1, line2 in zip(lines_diff, stdout.strip().split('\n')):
        if line1.startswith('---'):
            continue
        assert line1 == line2 + '\n'


def test_poselect():
    """Functional test for poselect"""
    with open(prepend_path('poselect_expected_output')) as file_:
        expected = file_.read()
    standardtest(['poselect', '-ft', FILE], expected)
