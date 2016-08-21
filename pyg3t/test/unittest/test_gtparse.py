# encoding: utf-8

"""Unit tests for the gtparse module"""

from __future__ import unicode_literals, print_function

import pytest

from common import stdin_fix
# Make sure there is a stdin with a buffer attribute during import
with stdin_fix():
    from pyg3t.util import PoError
    from pyg3t.gtparse import parse_header_data

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


### Tests

# NOTE: chunkwrap is not tested as it is used solely by wrap and we
# hope to use standard lib wrap in the future anyway



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


