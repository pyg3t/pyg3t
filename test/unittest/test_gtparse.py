# encoding: utf-8

"""Unit tests for the gtparse module"""

from __future__ import unicode_literals, print_function

from os import path

import pytest
try:
    from unittest.mock import MagicMock
except ImportError:
    from mock import MagicMock

from pyg3t.gtparse import (
    isstringtype, wrap, parse_header_data,  # _get_header
)

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


PARSE_HEADER_IN = (
    'a: æøå\\n'
    '\\n'  # blank line should be ignored
    'b: multiple words\\n'
    ' \\n'  # line with space should be ignored
    'c-key-with-multiple-words: 8\\n'
    'def'  # No key-value separator present, line (at present) also ignored
)
PARSE_HEADER_OUT = {
    'a': 'æøå', 'b': 'multiple words', 'c-key-with-multiple-words': '8'
}
#def test_parse_header():
#    """Test the parse_header function"""
#    print(parse_header_data(PARSE_HEADER_IN))
#    assert parse_header_data(PARSE_HEADER_IN) == PARSE_HEADER_OUT


# test _get_header
# def test__get_header():
#     """Test the _get_header function"""
#     # Form mock msgs
#     msgs = []
#     for n in range(3):
#         msg = MagicMock()
#         msg.meta = {}
#         msg.msgid = 'o'
#         msg.msgstr = 'h'
#         msgs.append(msg)

#     # test that having no header raises an exception
#     with pytest.raises(ValueError) as exception:
#         _get_header(msgs)
#     assert str(exception).endswith('Header not found in msgs')

#     # Test that it finds the header and fills in the metadata correctly
#     header = msgs[1]
#     header.msgid = ''
#     header.msgstr = PARSE_HEADER_IN
#     identified_header = _get_header(msgs)
#     assert header == identified_header
#     assert header.meta['headers'] == PARSE_HEADER_OUT
