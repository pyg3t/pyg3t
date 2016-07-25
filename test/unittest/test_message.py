
"""Unit tests for the message module"""

from os import path
import pytest

try:
    from unittest.mock import Mock
except ImportError:
    from mock import Mock

from pyg3t.message import (
    isstringtype, wrap,  Catalog
)
from test_gtparse import PARSE_HEADER_OUT


### Fixtures
@pytest.fixture
def msgs():
    """Make a list of mock msgs"""
    msgs = []
    for msgid in ('', 'a', 'b'):
        # Make sure the mock complains if we access any other attributes
        msg = Mock(spec_set=['msgid', 'is_obsolete', 'meta'])
        msg.msgid = msgid
        msg.is_obsolete = False
        msgs.append(msg)
    header_msg = msgs[0]
    header_msg.meta = {'headers': PARSE_HEADER_OUT}
    return msgs

### Tests
ISSTRINGTYPE = (('å', True), ('å'.encode('utf-8'), True), (1, False))
def test_isstringtype():
    """Test the isstriptype function"""
    for obj, expected_result in ISSTRINGTYPE:
        assert isstringtype(obj) is expected_result


def test_wrap():
    """Test the wrap function"""
    # Load in this files source (without newlines) as a test text
    with open(path.abspath(__file__), 'rb') as file_:
        content = file_.read().decode('utf-8').replace('\n', ' ')
    content_iter = (chunk for chunk in content.split(' ') if chunk != '')

    # Get the warpped lines
    wrapped_lines = wrap(content)
    # Test that no line is too long and that the original text and the
    # wrapped lines consist of the same "words"
    for line in wrap(content):
        assert len(line) < 78
        for wrap_chunk in line.split(' '):
            if wrap_chunk == '':
                continue
            assert wrap_chunk == next(content_iter)


class TestCatalog(object):
    """Test the Catalog class"""

    def test___init__(self, msgs):
        """Test the __init__ method___"""
        # Test normal __init__ and sorting into msgs and obsoletes
        msgs[1].is_obsolete = True
        catalog = Catalog('filename', 'encoding', msgs, 'trailing_comment')
        assert catalog.fname == 'filename'
        assert catalog.encoding == 'encoding'
        obsoletes = [msgs.pop(1)]
        assert catalog.msgs == msgs
        assert catalog.obsoletes == obsoletes
        assert catalog.headers == PARSE_HEADER_OUT
        assert catalog.trailing_comments == 'trailing_comment'

        # Test trailin_comments default
        catalog = Catalog('filename', 'encoding', msgs)
        assert catalog.trailing_comments is None
