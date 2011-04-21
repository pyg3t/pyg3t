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

"""
podiff whiteboard

Succes criteria:
================
(v) ignore false diff by default
(v) use python difflib
     allow for custom diff output format
(v) allow for files with different base, i.e. diff against newer version
(v)   via relax option
    multiple file diff
(v) allow for definition of output file
(v)  check that it is not the same as one of the input files
(v) Give option for line numbers
    Use optionparser.error for error messages


Implementation:
===============
"""

# XXX
# Diffing files with different encodings
# To compare strings, they should have same encoding.
# My suggestion (Ask) is to not do anything if they do happen to have
# same encoding from the start, but if they do not, then convert
# both to utf8.

import sys
from optparse import OptionParser
from difflib import unified_diff
from pyg3t.gtparse import parse
from pyg3t import __version__

def build_parser():
    description = ('Prints the difference between two po-FILES in chunks'
                   'of diff output that pertain to one original string')

    usage = '%prog [OPTIONS] ORIGINAL_FILE UPDATED_FILE'
    parser = OptionParser(usage=usage, description=description,
                          version=__version__)

    parser.add_option('-l', '--line-numbers', action='store_true', default=True,
                      dest='line_numbers',
                      help='prefix line number of the msgid in the original '
                      'file to the diff chunks')
    parser.add_option('-m', '--no-line-numbers', action='store_false',
                      dest='line_numbers',
                      help='do not prefix line number (opposite of -l)')
    parser.add_option('-o', '--output',
                      help='file to send the diff output to, instead of '
                      'standard out')
    parser.add_option('-r', '--relax', action='store_true', default=False,
                      help='allow for files with different base, i.e. '
                      'where the msgids are not pairwise the same. But still '
                      'make the output proofread friendly')
    parser.add_option('-s', '--strict', action='store_false', dest='relax',
                      help='do not allow for files with different base '
                      '(opposite of -r)')
    parser.add_option('-f', '--full', action='store_true', default=False,
                      help='like --relax but show the full diff including the '
                      'entries that are only present in the original file')
    return parser

class PoDiff:
    def __init__(self, out, in_orig, in_new):
        self.out = out
        self.in_orig = in_orig
        self.in_new = in_new
        self.number_of_diff_chunks = 0
        self.show_line_numbers = None

    def check_files_common_base(self, loe, lne):
        # loe = list_orig_entries  ###  lne = list_new_entries
        similar = True

        # Easy check if length is the same
        if len(loe) != len(lne):
            similar = False
        # If the length is the same, compare msgids and msgctxt pairwise
        # to determine if the files have identical base
        else:
            for oe, ne in zip(loe, lne):
                if (oe.msgid != ne.msgid or oe.hasplurals != ne.hasplurals or
                    oe.msgctxt != ne.msgctxt):
                    similar = False
        return similar

    def dict_entries(self, list_entries):
        # Make a dictionary out of a list of entries for faster multiple
        # searches
        dict_entries = {}
        for entry in list_entries:
            dict_entries[entry.msgid] = entry
        return dict_entries

    def diff_files_relaxed(self, list_orig_entries, list_new_entries, full=False):
        # Turn orig entries into dictionary
        dict_orig_entries = self.dict_entries(list_orig_entries)

        # Walk throug the list of new entries
        for new_entry in list_new_entries:
            # and if the new entry msgid is also found in the orig
            if dict_orig_entries.has_key(new_entry.msgid):
                # ask it to be diffed ...
                self.diff_two_entries(dict_orig_entries[new_entry.msgid],
                                      new_entry)
                # ... and set it to None in orig mesages, so that we know
                # which ones we have used
                dict_orig_entries[new_entry.msgid] = None
            else:
                # output diff showing only the new entry
                self.diff_one_entry(new_entry, entry_is='new')

        # If we ar making the full diff, diff the entries that are only
        # present in original file (the ones that are not None in
        # dict_orig_entries)
        if full:
            for key in dict_orig_entries.keys():
                if dict_orig_entries[key]:
                    # output diff showing only the old entry
                    self.diff_one_entry(dict_orig_entries[key],\
                                            entry_is='orig')

        self.print_status()

    def diff_files_unrelaxed(self, list_orig_entries, list_new_entries):
        for orig_entry, new_entry in zip(list_orig_entries, list_new_entries):
            self.diff_two_entries(orig_entry, new_entry)
        self.print_status()

    def diff_two_entries(self, orig_entry, new_entry):
        # Check if the there is a reason to diff
        if orig_entry.isfuzzy is not new_entry.isfuzzy or\
                ''.join(orig_entry.msgstrs) != ''.join(new_entry.msgstrs) or\
                ''.join(orig_entry.get_comments('# ')) !=\
                ''.join(new_entry.get_comments('# ')):

            # Possibly output the line number of the msgid in the new file
            if self.show_line_numbers:
                print >> self.out, self.header(new_entry.meta['lineno'],
                                               self.in_new)

            # Make the diff
            diff = list(unified_diff(orig_entry.meta['rawlines'], 
                                     new_entry.meta['rawlines'],
                                     n=10000))
            # and print the result, without the 3 lines of header and increment
            # the chunk counter
            print >> self.out, ''.join(diff[3:])
            self.number_of_diff_chunks += 1

    def diff_one_entry(self, entry, entry_is):
        """ produce diff if only one entry is present

        Keyword:
        entry_is   can be either 'new' or 'orig'
        """
        # Possibly output the line number of the msgid in the new file
        source = self.in_orig if entry_is == 'orig' else self.in_new
        if self.show_line_numbers:
            print >> self.out, self.header(entry.meta['lineno'], source)

        # Make the diff
        if entry_is == 'new':
            diff = list(unified_diff('', entry.meta['rawlines'], n=10000))
        elif entry_is == 'orig':
            diff = list(unified_diff(entry.meta['rawlines'], '', n=10000))
        # and print the result, without the 3 lines of header and increment
        # the chunk counter
        print >> self.out, ''.join(diff[3:]).encode('utf8')
        self.number_of_diff_chunks += 1
            
    def header(self, linenumber, source):
        return ('--- Line %d (%s) ' % (linenumber, source)).ljust(32, '-')

    def print_status(self):
        bar = ' ' + '=' * 77
        print >> self.out, bar
        print >> self.out, " Number of messages:",\
            self.number_of_diff_chunks
        print >> self.out, bar

def main():
    """The main class loads the files and output the diff"""

    files_are_similar = True

    option_parser = build_parser()
    opts, args = option_parser.parse_args()

    # We need exactly two files to proceed
    if len(args) != 2:
        # Give a parser error and return with exit code 2
        option_parser.error('podiff takes exactly two arguments')

    # Give an error if the specified output file is the same as one of the
    # input files
    if opts.output is not None:
        if (opts.output == args[0]) or (opts.output == args[1]):
            # Give a parser error and return with exit code 2
            option_parser.error('The output file you have specified is the '
                                'same as one of the input files. This is not '
                                'allowed, as it may cause a loss of work.')
            
        # Try and open file for writing, if it does not succeed, give error
        # and exit
        try:
            out = open(opts.output, 'w')
        except IOError, err:
            print >> sys.stderr, ('Could not open output file for writing. '
                                  'open() gave the following error:')
            print >> sys.stderr, err
            raise SystemExit(4)
    else:
        out = sys.stdout        

    # Get PoDiff instanse
    podiff = PoDiff(out, args[0], args[1])
    # Overwrite settings with system wide settings
         
    # Overwrite settings with commands line arguments
    podiff.show_line_numbers = opts.line_numbers
    
    # Load files
    try:
        list_orig_entries = list(parse(open(args[0])))
        list_new_entries = list(parse(open(args[1])))
    except IOError, err:
        print >> sys.stderr, ('Could not open one of the input files for '
                              'reading. open() gave the following error:')
        print >> sys.stderr, err
        raise SystemExit(5)

    # If we don't relax or do full diff (which also implies relax), check if
    # they are dissimilar
    if not (opts.relax or opts.full):
        files_are_similar = podiff.check_files_common_base(list_orig_entries,
                                                           list_new_entries)
        # and if they indeed are dissimilar, give and error
        if not files_are_similar:
            option_parser.error('Cannot work with files with dissimilar base, '
                                'unless the relax option (-r) or the full '
                                'options (-f) is used.\n\nNOTE: This is not '
                                'recommended..!\nMaking a podiff for '
                                'proofreading should happen between files '
                                'with similar base, to make the podiff easier '
                                'to read.')
            
    if opts.relax or opts.full:
        podiff.diff_files_relaxed(list_orig_entries, list_new_entries,\
                                      opts.full)
    else:
        podiff.diff_files_unrelaxed(list_orig_entries, list_new_entries)

    return
  
#################################
if __name__ == '__main__':
    main()
