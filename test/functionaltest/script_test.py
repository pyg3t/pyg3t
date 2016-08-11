# encoding: utf-8

"""This module performs functional tests of the pyg3t tools."""

from __future__ import unicode_literals

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
    assert stderr == b''
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
    assert stderr == b''
    with open(prepend_path('gtcat_expected_output'), 'rb') as file_:
        expected = file_.read()
    assert stdout == expected


def test_gtcheckargs():
    """Functional test for gtcheckargs"""
    with open(prepend_path('gtcheckargs_expected_output'), 'rb') as file_:
        expected = file_.read()
    standardtest(['gtcheckargs', FILE], expected, return_code=1)


def test_gtcompare():
    """Functional test for gtcompare"""
    with open(prepend_path('gtcompare_expected_output'), 'rb') as file_:
        expected = file_.read()
    standardtest(['gtcompare', FILE, FILE], expected)


def test_gtgrep():
    """functional test for gtgrep"""
    with open(prepend_path('gtgrep_expected_output'), 'rb') as file_:
        expected = file_.read()
    standardtest(['gtgrep', '-i', 'hello', '-s', 'hej', FILE], expected)


def test_gtmerge():
    """Functional test for gtmerge"""
    with open(prepend_path('gtmerge_expected_output'), 'rb') as file_:
        expected = file_.read()
    standardtest(['gtmerge', FILE, FILE], expected)


def test_gtprevmsgdiff():
    """Functional test for gtprevmsgdiff"""
    with open(prepend_path('gtprevmsgdiff_expected_output'), 'rb') as file_:
        expected = file_.read()
    standardtest(['gtprevmsgdiff', FILE], expected)


def test_gtwdiff():
    """Functional test for gtwdiff"""
    with open(prepend_path('gtwdiff_expected_output'), 'rb') as file_:
        expected = file_.read()
    return_code, stdout, stderr = run_command(
        ['gtwdiff', 'testpodiff_gtwdiff.podiff']
    )
    assert return_code == 0
    assert stderr == b''

    # We have problems with the diff comming out in different order on
    # different Python versions, so test for correct in and out but
    # not for the same order
    new_pattern = b'\x1b[1;33;42m'
    old_pattern = b'\x1b[1;31;41m'
    stop_pattern = b'\x1b[0m'
    def parse_wdiff(text):
        out = {'new': b'', 'old': b'', 'unchanged': b''}
        state = 'unchanged'
        while text:
            print(len(text))
            if text.startswith(new_pattern):
                state = 'new'
                text = text.replace(new_pattern, b'', 1)
            elif text.startswith(old_pattern):
                state = 'old'
                text = text.replace(old_pattern, b'', 1)
            elif text.startswith(stop_pattern):
                state = 'unchanged'
                text = text.replace(stop_pattern, b'', 1)
            else:
                out[state] += text[0:1]
                text = text[1:]
        return out
    from_stdout = parse_wdiff(stdout)
    from_expected = parse_wdiff(expected)
    assert from_stdout['new'] == from_expected['new']
    assert from_stdout['old'] == from_expected['old']
    assert from_stdout['unchanged'] == from_expected['unchanged']

    


def test_gtxml():
    """Functional test for gtxml"""
    with open(prepend_path('gtxml_expected_output'), 'rb') as file_:
        expected = file_.read()
    standardtest(['gtxml', FILE], expected, return_code=1)

def test_poabc():
    """Functional test for poabc"""
    with open(prepend_path('poabc_expected_output'), 'rb') as file_:
        expected = file_.read()
    standardtest(['poabc', FILE], expected)


def test_podiff():
    """Functional test for podiff"""
    with open(prepend_path('podiff_expected_output'), 'rb') as file_:
        expected = file_.read()
    standardtest(['podiff', '--relax', 'old.po', 'new.po'], expected)


def test_popatch():
    """Functional test for popatch"""
    return_code, stdout, stderr = run_command(
        ['popatch', 'testpofile.da.po', 'testpodiff.podiff'])
    assert return_code == 0
    assert stderr == b''
    with open(prepend_path('patched.po'), 'wb') as file_:
        file_.write(stdout)

    return_code, stdout, stderr = run_command(
        ['popatch', '--new', 'testpodiff.podiff'])
    assert return_code == 0
    assert stderr == b''
    with open(prepend_path('patched.new.po'), 'wb') as file_:
        file_.write(stdout)

    return_code, stdout, stderr = run_command(
        ['popatch', '--old', 'testpodiff.podiff'])
    assert return_code == 0
    assert stderr == b''
    with open(prepend_path('patched.old.po'), 'wb') as file_:
        file_.write(stdout)

    return_code, stdout, stderr = run_command(
        ['podiff', '-rf', 'patched.old.po', 'patched.new.po'])
    assert return_code == 0
    assert stderr == b''
    with open(prepend_path('testpodiff.podiff'), 'rb') as file_:
        lines_diff = file_.readlines()

    lines_stdout = stdout.strip().split(b'\n')
    for line1, line2 in zip(lines_diff, lines_stdout):
        if line1.startswith(b'---'):
            continue
        assert line1 == line2 + b'\n'


def test_poselect():
    """Functional test for poselect"""
    with open(prepend_path('poselect_expected_output'), 'rb') as file_:
        expected = file_.read()
    standardtest(['poselect', '-ft', FILE], expected)
