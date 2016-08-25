#!/usr/bin/env python
"""
podiff -- A gettext diff module in Python
Copyright (C) 2009-2011 Kenneth Nielsen <k.nielsen81@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from __future__ import print_function, unicode_literals
from optparse import OptionParser
from difflib import unified_diff
from pyg3t.gtparse import parse
from pyg3t import __version__
from pyg3t.gtdifflib import FancyWDiffFormat
from pyg3t.gtdifflib import diff as wdiff
from pyg3t.util import pyg3tmain, get_encoded_output, get_bytes_input


class PoDiff:

    """Description of the PoDiff class"""

    def __init__(self, out, show_line_numbers=False, color=False):
        """Initialize class variables

        Keywords:
        out        A file like object that the output will be printed to
        show_line_numbers
                   boolean, whether to show the line numbers from the new
                   catalog object in a header line above each diff piece
        """
        self.out = out
        self.number_of_diff_chunks = 0
        self.show_line_numbers = show_line_numbers
        self.color = color
        if self.color:
            self.wdiff_formatter = FancyWDiffFormat()

    @staticmethod
    def catalogs_have_common_base(old_cat, new_cat):
        """Check if catalogs have common base

        Keywords:
          old_cat    old catalog
          new_cat    new catalog
        """

        def getkeys(cat):
            return set(msg.key for msg in cat.iter(trailing=False))

        old_keys = getkeys(old_cat)
        new_keys = getkeys(new_cat)
        return old_keys == new_keys

    def diff_catalogs_relaxed(self, old_cat, new_cat, full_diff=False):
        """Diff catalogs relaxed. I.e. accept differences in base.

        Keywords:
        old_cat    old catalog
        new_cat    new catalog
        full_diff  boolean, show msg's unique to old_cat
        """
        dict_old_cat = old_cat.dict(obsolete=True)

        # Make diff for all the msg's in new_cat
        # XXX trailing comments!
        for new_msg in new_cat.iter(trailing=False):
            if new_msg.key in dict_old_cat:
                self.diff_two_msgs(dict_old_cat[new_msg.key], new_msg,
                                   fname=new_cat.fname)
            else:
                self.diff_one_msg(new_msg, is_new=True, fname=new_cat.fname)

        # If we are making the full diff, diff the entries that are only
        # present in old file
        if full_diff:
            dict_new_cat = new_cat.dict(obsolete=True)
            only_old = [key for key in dict_old_cat if key not in
                        dict_new_cat]

            for key in only_old:
                self.diff_one_msg(dict_old_cat[key], is_new=False,
                                  fname=old_cat.fname)

        self.print_status()

    def diff_catalogs_strict(self, old_cat, new_cat):
        """Diff catalogs strict. I.e. enforce common base

        Keywords:
        old_cat    old catalog
        new_cat    new catalog
        """
        for old_msg, new_msg in zip(old_cat, new_cat):
            self.diff_two_msgs(old_msg, new_msg, fname=new_cat.fname)
        self.print_status()

    def diff_two_msgs(self, old_msg, new_msg, fname=None):
        """Produce diff between two messages

        Keywords:
        old_msg    old message
        new_msg    new message
        new_cat    new catalog (Used to get the filename for the line number
                   header)
        """

        re_enc_old_msgstrs = old_msg.msgstrs
        re_enc_old_comments = old_msg.get_comments('# ')

        # Check if the there is a reason to diff.
        # NOTE: Last line says we always show header
        if (old_msg.isfuzzy != new_msg.isfuzzy or
            re_enc_old_msgstrs != new_msg.msgstrs or
            re_enc_old_comments != new_msg.get_comments('# ') or
            new_msg.msgid == ''):

            if self.show_line_numbers:
                print(self.__print_lineno(new_msg, fname), file=self.out)

            if self.color:
                self.diff_two_msgs_color(old_msg, new_msg)
                return

            old_lines = old_msg.meta['rawlines']
            diff = list(unified_diff(old_lines, new_msg.meta['rawlines'],
                                     n=10000))

            if len(diff) == 0 and new_msg.msgid == '':
                self.__print_header(new_msg)
            else:
                # Print the result, without the 3 lines of header
                print(''.join(diff[3:]), file=self.out)

            if new_msg.msgid != '':
                self.number_of_diff_chunks += 1

    def diff_two_msgs_color(self, old_msg, new_msg):
        new_msg.comments = wdiff('\0'.join(old_msg.comments),
                                 '\0'.join(new_msg.comments),
                                 self.wdiff_formatter).split('\0')
        if new_msg.has_context:
            assert old_msg.has_context
            new_msg.msgctxt = wdiff(old_msg.msgctxt, new_msg.msgctxt,
                                    self.wdiff_formatter)
        new_msg.msgid = wdiff(old_msg.msgid, new_msg.msgid,
                              self.wdiff_formatter)
        if new_msg.isplural:
            assert old_msg.isplural
            new_msg.msgid_plural = wdiff(old_msg.msgid_plural,
                                         new_msg.msgid_plural,
                                         self.wdiff_formatter)

        assert len(old_msg.msgstrs) == len(new_msg.msgstrs)
        for i, (msgstr1, msgstr2) in enumerate(zip(old_msg.msgstrs,
                                                   new_msg.msgstrs)):
            new_msg.msgstrs[i] = wdiff(msgstr1, msgstr2, self.wdiff_formatter)

        print(new_msg.tostring(), file=self.out)

        if new_msg.msgid != '':
            self.number_of_diff_chunks += 1

    def __print_header(self, msg):
        """ Prints out the header when there is no diff in it """
        for line in msg.meta['rawlines']:
            print(' ' + line, end='', file=self.out)
        # Ugh.  Empty print causes unicode type error in Py2.
        # XXX better solution?
        print('', file=self.out)

    def diff_one_msg(self, msg, is_new, fname=None):
        """Produce diff if only one entry is present

        Keywords:
        msg        message
        cat        catalog
        is_new     boolean
        """
        if self.show_line_numbers:
            print(self.__print_lineno(msg, fname), file=self.out)

        # Make the diff
        msg_lines = msg.meta['rawlines']
        if is_new:
            diff = list(unified_diff('', msg_lines, n=10000))
        else:
            diff = list(unified_diff(msg_lines, '', n=10000))

        # Print the result without the 3 lines of header
        print(''.join(diff[3:]), file=self.out)
        self.number_of_diff_chunks += 1

    @staticmethod
    def __print_lineno(msg, fname=None):
        """Print line number and file name header for diff of msg pairs"""
        lineno = msg.meta['lineno'] if 'lineno' in msg.meta else 'N/A'
        return ('--- Line %d (%s) ' % (lineno, fname)).ljust(32, '-')

    def print_status(self):
        """Print the number of diff pieces that have been output"""
        sep = ' ' + '=' * 77
        print(sep, file=self.out)
        print(' Number of messages: %d' %
              self.number_of_diff_chunks, file=self.out)
        print(sep, file=self.out)


def __build_parser():
    """ Builds the options """
    description = ('Prints the difference between two po-FILES in pieces '
                   'of diff output that pertain to one original string. '
                   )

    usage = ('%prog [OPTIONS] ORIGINAL_FILE UPDATED_FILE\n\n'
             'Use - as file argument to use standard in')
    parser = OptionParser(usage=usage, description=description,
                          version=__version__)

    parser.add_option('-l', '--line-numbers', action='store_true',
                      default=True, dest='line_numbers',
                      help='prefix line number of the msgid in the original '
                      'file to the diff chunks')
    parser.add_option('-m', '--no-line-numbers', action='store_false',
                      dest='line_numbers',
                      help='do not prefix line number (opposite of -l)')
    parser.add_option('-o', '--output', metavar='FILE', default='-',
                      help='send output to FILE instead of '
                      'standard out')
    parser.add_option('-r', '--relax', action='store_true', default=False,
                      help='allow for files with different base, i.e. '
                      'where the msgids are not pairwise the same. But still '
                      'make the output proofread friendly.')
    parser.add_option('-s', '--strict', action='store_false', dest='relax',
                      help='do not allow for files with different base '
                      '(opposite of -r)')
    parser.add_option('-f', '--full', action='store_true', default=False,
                      help='like --relax but show the full diff including the '
                      'entries that are only present in the original file')
    parser.add_option('-c', '--color', action='store_true', default=False,
                      help='make a wordwise diff and use markers to highlight '
                      'it')
    return parser


@pyg3tmain(__build_parser)
def main(option_parser):  # pylint: disable-msg=R0912
    """The main function loads the files and outputs the diff"""

    opts, args = option_parser.parse_args()

    # We need exactly two files to proceed
    if len(args) != 2:
        option_parser.error('podiff takes exactly two arguments')

    # Load files into catalogs
    cat_old = parse(get_bytes_input(args[0]))
    cat_new = parse(get_bytes_input(args[1]))

    if opts.output != '-' and opts.output in (args[0], args[1]):
        option_parser.error('The output file you have specified is the '
                            'same as one of the input files. This is not '
                            'allowed, as it may cause a loss of work.')

    out = get_encoded_output(cat_new.encoding, opts.output)

    podiff = PoDiff(out, opts.line_numbers, opts.color)

    # Diff the files
    if opts.relax or opts.full:
        podiff.diff_catalogs_relaxed(cat_old, cat_new, opts.full)
    else:
        if not podiff.catalogs_have_common_base(cat_old, cat_new):
            option_parser.error('Cannot work with files with dissimilar base, '
                                'unless the relax option (-r) or the full '
                                'options (-f) is used.\n\nNOTE: This is not '
                                'recommended..!\nMaking a podiff for '
                                'proofreading should happen between files '
                                'with similar base, to make the podiff easier '
                                'to read.')

        podiff.diff_catalogs_strict(cat_old, cat_new)
