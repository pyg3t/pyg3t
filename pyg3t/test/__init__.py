"""__init__ file for the test sub package

Provides convinience functions to run the tests programatically

"""

from os import chdir
from os.path import abspath, dirname, join
import pytest


def _run_tests(path_addition, command_line_opts):
    """Run tests"""
    # Add the path of the test folder to the argument line and
    # possibly limit to the tests in the path_addition folder
    argument_line = dirname(abspath(__file__))
    if path_addition:
        argument_line = join(argument_line, path_addition)
    # If extra command line arguments are provided, add them
    if command_line_opts:
        argument_line += ' ' + command_line_opts
    pytest.main(argument_line)


def run(command_line_opts=None):
    """Run all tests

    Args:
        command_line_opts (unicode): Extra command line arguments to pytest.
            Run 'py.test --help' at the command line to see all available
            options
    """
    _run_tests(None, command_line_opts)


def run_unittest(command_line_opts=None):
    """Run unit tests

    Args:
        command_line_opts (unicode): See doc string for :func:`run`
    """
    _run_tests('unittest', command_line_opts)


def run_functionaltest(command_line_opts=None):
    """Run functional tests

    Args:
        command_line_opts (unicode): See doc string for :func:`run`
    """
    _run_tests('functionaltest', command_line_opts)
