# encoding: utf-8

"""Unit tests for the gtparse module"""

from __future__ import unicode_literals, print_function

from os import path

import pytest
try:
    from unittest.mock import Mock
except ImportError:
    from mock import Mock

from pyg3t.util import PoError
from pyg3t.gtparse import parse_header_data
from pyg3t.message import (
    isstringtype, wrap,  Catalog
)

### Test data
PARSE_HEADER_IN_ERROR = (
    'a: æøå\\n'
    '\\n'  # blank line should be ignored
    'b: multiple words\\n'
    ' \\n'  # line with space should be ignored
    'c-key-with-multiple-words: 8\\n'
    'def'  # No key-value separator present, line (at present) also ignored
)
PARSE_HEADER_IN = PARSE_HEADER_IN_ERROR +\
                  '\\nContent-Type: text/plain; charset=UTF-8'
PARSE_HEADER_OUT = {
    'a': 'æøå', 'b': 'multiple words', 'c-key-with-multiple-words': '8',
    'Content-Type': 'text/plain; charset=UTF-8',
}


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

# NOTE: chunkwrap is not tested as it is used solely by wrap and we
# hope to use standard lib wrap in the future anyway

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


def test_parse_header():
    """Test the parse_header function"""
    # Should raise if there is no Content-Type in header
    with pytest.raises(PoError) as exception:
        parse_header_data(PARSE_HEADER_IN_ERROR)
    assert exception.value.errtype == 'no-content-type'

    # Should raise if there is Content-Type but the charset cannot be
    # extracter
    header = PARSE_HEADER_IN_ERROR + '\\nContent-Type:'
    with pytest.raises(PoError) as exception:
        parse_header_data(header)
    assert exception.value.errtype == 'no-charset'

    # Should raise if there is a charset, but not a known one
    header = PARSE_HEADER_IN_ERROR +\
             '\\nContent-Type: text/plain; charset=UTF-15'
    with pytest.raises(PoError) as exception:
        parse_header_data(header)
    assert exception.value.errtype == 'bad-charset'

    # Test proper parse of correct header
    assert parse_header_data(PARSE_HEADER_IN) == ('utf-8', PARSE_HEADER_OUT)


# TODO: Test DuplicateMessageError


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

