
"""Common tools for unit testing pyg3t"""

import sys
from contextlib import contextmanager
try:
    from unittest.mock import Mock
except ImportError:
    from mock import Mock

@contextmanager
def stdin_fix():
    """Context manager to replace stdin with Mock to make sure it has
    a buffer property

    """
    old_stdin = sys.stdin
    sys.stdin = Mock()
    yield
    sys.stdin = old_stdin
