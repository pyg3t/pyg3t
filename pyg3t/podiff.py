#!/usr/bin/env python
"""
podiff -- A gettext diff module in Python
Copyright (C) 2009 Kenneth Nielsen <k.nielsen81@gmail.com>

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


podiff whiteboard

Succes criteria:
================
(v) ignore false diff by default
(v) use python difflib
     allow for custom diff output format
(v) allow for files with different base, i.e. diff against newer version
(v)   via relax option
    multiple file diff
    allow for definition of output file
     check that it is not the same as one of the input files
    Give option for line numbers
    Use optionparser.error for error messages


Implementation:
===============
"""

import sys
from optparse import OptionParser
from difflib import unified_diff
from pyg3t.gtparse import Parser
from pyg3t import __version__

def build_parser():
    description = ('Prints the difference between two po-FILES in chunks'
                   'of diff output that pertain to one original string')

    usage = '%prog [OPTIONS] ORIGINAL_FILE UPDATED_FILE'
    parser = OptionParser(usage=usage, description=description,
                          version=__version__)

    parser.add_option('-r', '--relax', action='store_true',
                      help='allows for files with different base, i.e. '
                      'where the msgids are not pairwise the same')
    parser.add_option('-o', '--output-file',
                      help='file to send the diff output to, instead of '
                      'standard out')
    return parser

class PoDiff:
    def __init__(self, out):
        self.out = out
        self.number_of_diff_chunks=0

    def check_files_common_base(self, loe, lne):
        # loe = list_orig_entries
        # lne = list_new_entries
        similar=True

        # Easy check if length is the same
        if len(loe) != len(lne):
            similar=False
        # If the length is the same, compare msgids and static comments pairwise
        # to determine if the files have identical base
        else:
            for oe, ne in zip(loe, lne):
                if oe.msgid != ne.msgid or\
                        oe.hasplurals != ne.hasplurals or\
                        oe.msgctxt != ne.msgctxt or\
                        ''.join(oe.getcomments('#.')) !=\
                        ''.join(ne.getcomments('#.')) or\
                        ''.join(oe.getcomments('#:')) !=\
                        ''.join(ne.getcomments('#:')) or\
                        ''.join(oe.getcomments('#|')) !=\
                        ''.join(ne.getcomments('#|')):
                    similar=False
        return similar

    def diff_files_relaxed(self, list_orig_entries, list_new_entries):
        # Make a dictionary out of the old entries to easen multiple searches
        # for strings
        dict_orig_entries={}
        for entry in list_orig_entries:
            dict_orig_entries[entry.msgid]=entry

        # Walk throug the list of new entries
        for new_entry in list_new_entries:
            # and if the new entry msgid is also found in the orig
            if dict_orig_entries.has_key(new_entry.msgid):
                # ask it to be diffed
                self.diff_two_entries(dict_orig_entries[new_entry.msgid],
                                      new_entry)
        self.print_status()

    def diff_files_unrelaxed(self, list_orig_entries, list_new_entries):
        for orig_entry, new_entry in zip(list_orig_entries, list_new_entries):
            self.diff_two_entries(orig_entry, new_entry)
        self.print_status()

    def diff_two_entries(self, orig_entry, new_entry):
        # Check if the there is a reason to diff
        if orig_entry.isfuzzy is not new_entry.isfuzzy or\
                ''.join(orig_entry.msgstrs) != ''.join(new_entry.msgstrs) or\
                ''.join(orig_entry.getcomments('# ')) !=\
                ''.join(new_entry.getcomments('# ')):
            # Make the diff and print the result, without the 3 lines of header
            # and increment the chunk counter
            diff = list(unified_diff(orig_entry.rawlines,new_entry.rawlines,
                                     n=10000))
            print >> self.out, ''.join(diff[3:]).encode('utf8')
            self.number_of_diff_chunks=self.number_of_diff_chunks+1

    def print_status(self):
        print >> self.out, " ============================================================================="
        print >> self.out, " Number of messages:",\
            self.number_of_diff_chunks
        print >> self.out, " ============================================================================="


def main():
    """The main class loads the files and output the diff
    """

    errors={'1':'podiff takes exactly two arguments.',
            '2':'The output file you have specified is the same as '\
                'one of the input files. This is not allowed, as it '\
                'may cause a loss of work.',
            #FIXME
            '3':'Cannot work with files with dissimilar base, unless the '\
                'relax option (-r) is used.\n\nNOTE: This is not recommended..!\n'\
                'Making a podiff for proofreading should happen between '\
                'files with similar base, to make the podiff easier to read.',
            '4':'Could not open output file for writing. open() gave the '\
                'following error:',
            '5':'Could not open one of the input files for reading. open() '\
                'gave the following error:'}

    files_are_similar = True

    parser = build_parser()
    opts, args = parser.parse_args()

    # We need exactly two files to proceed
    if len(args) != 2:
        # System exit with error code
        print errors['1']
        # FIXME handle exit codes properly
        sys.exit(1)

    # Give an error if the specified output file is the same as one of the
    # input files
    if opts.output_file is not None:
        if (opts.output_file == args[0]) or (opts.output_file == args[1]):
            print errors['2']
            sys.exit(2)
        # Try and open file for writing, if it does not succeed, give error
        # and exit
        try:
            out = open(opts.output_file, 'w')
        except IOError, msg:
            print errors['4']
            print msg
            sys.exit(4)
    else:
        out = sys.stdout        

    podiff = PoDiff(out)        

    # Load files
    # FIXME give this another name, so that it doesn't overwrite optionparser
    parser = Parser()
    
    try:
        list_orig_entries = list(parser.parse_asciilike(open(args[0])))
        list_new_entries = list(parser.parse_asciilike(open(args[1])))
    except IOError, err:
         print errors['5']
         print err
         sys.exit(5)

    # If we don't relax, check if they are dissimilar
    if not opts.relax:
        files_are_similar = podiff.check_files_common_base(list_orig_entries,
                                                           list_new_entries)

    # If we don't relax and the files are dissimilar, give and error
    if not opts.relax and not files_are_similar:
        print errors['3']
        sys.exit(3)

    if opts.relax:
        podiff.diff_files_relaxed(list_orig_entries, list_new_entries)
    else:
        podiff.diff_files_unrelaxed(list_orig_entries, list_new_entries)

    return
  
#################################
if __name__ == '__main__':
    main()
