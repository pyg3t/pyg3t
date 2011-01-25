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
                      help='show the full diff including the entries that are '
                      'only present in the original file (as opposed to '
                      '--relaz')
    return parser

class PoDiff:
    def __init__(self, out):
        self.out = out
        self.number_of_diff_chunks=0
        self.show_line_numbers=None

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
                        ''.join(oe.get_comments('#.')) !=\
                        ''.join(ne.get_comments('#.')) or\
                        ''.join(oe.get_comments('#:')) !=\
                        ''.join(ne.get_comments('#:')) or\
                        ''.join(oe.get_comments('#|')) !=\
                        ''.join(ne.get_comments('#|')):
                    similar=False
        return similar

    def dict_entries(self, list_entries):
        # Make a dictionary out of a list of entries for faster multiple
        # searches
        dict_entries={}
        for entry in list_entries:
            dict_entries[entry.msgid]=entry
        return dict_entries

    def diff_files_relaxed(self, list_orig_entries, list_new_entries, full=False):
        # Turn orig entries into dictionary
        dict_orig_entries = self.dict_entries(list_orig_entries)

        # Walk throug the list of new entries
        for new_entry in list_new_entries:
            # and if the new entry msgid is also found in the orig
            if dict_orig_entries.has_key(new_entry.msgid):
                # ask it to be diffed
                self.diff_two_entries(dict_orig_entries[new_entry.msgid],
                                      new_entry)
                # ... and set it to None in orig mesages, so that we know
                # which ones we have used
                dict_orig_entries[new_entry.msgid] = None
            else:
                # output diff showing only the new entry
                diff_one_entry(new_entry, entry_is='new')

        # If we ar making the full diff, diff the entries that are only
        # present in original file (the ones that are not None in
        # dict_orig_entries)
        if full:
            for key in dict_orig_entries.keys():
                if dict_orig_entries[key]:
                    # output diff showing only the old entry
                    diff_one_entry(dict_orig_entries[key])

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
                print >> self.out, self.header(new_entry.linenumber)

            # Make the diff
            diff = list(unified_diff(orig_entry.rawlines,new_entry.rawlines,
                                     n=10000))
            # and print the result, without the 3 lines of header and increment
            # the chunk counter
            print >> self.out, ''.join(diff[3:]).encode('utf8')
            self.number_of_diff_chunks += 1

    def diff_one_entry(self, entry, entry_is):
        """ produce diff if only one entry is present

        Keyword:
        entry_is   can be either 'new' or 'orig'
        """
        # Make the diff
        if entry_is == 'new':
            diff = list(unified_diff('', entry.rawlines, n=10000))
        elif entry_is == 'orig':
            diff = list(unified_diff(entry.rawlines, '', n=10000))
        # and print the result, without the 3 lines of header and increment
        # the chunk counter
        print >> self.out, ''.join(diff[3:]).encode('utf8')
        self.number_of_diff_chunks += 1
            
    def header(self, linenumber):
        return ('--- Line %d (new file) ' % linenumber).ljust(32, '-')

    def print_status(self):
        bar = ' ' + '=' * 77
        print >> self.out, bar
        print >> self.out, " Number of messages:",\
            self.number_of_diff_chunks
        print >> self.out, bar

def main():
    """The main class loads the files and output the diff"""

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

    option_parser = build_parser()
    opts, args = option_parser.parse_args()

    # We need exactly two files to proceed
    if len(args) != 2:
        # System exit with error code
        print errors['1']
        # FIXME handle exit codes properly
        sys.exit(1)

    # Give an error if the specified output file is the same as one of the
    # input files
    if opts.output is not None:
        if (opts.output == args[0]) or (opts.output == args[1]):
            print errors['2']
            sys.exit(2)
        # Try and open file for writing, if it does not succeed, give error
        # and exit
        try:
            out = open(opts.output, 'w')
        except IOError, msg:
            print errors['4']
            print msg
            sys.exit(4)
    else:
        out = sys.stdout        

    # Get PoDiff instanse
    podiff = PoDiff(out)
    # Overwrite settings with system wide settings
         
    # Overwrite settings with commands line arguments
    podiff.show_line_numbers = opts.line_numbers
    
    # Load files
    gt_parser = Parser()
    try:
        list_orig_entries = list(gt_parser.parse(open(args[0])))
        list_new_entries = list(gt_parser.parse(open(args[1])))
    except IOError, err:
        print errors['5']
        print err
        sys.exit(5)

    # If we don't relax or do full diff (which also implies relax), check if
    # they are dissimilar
    if not (opts.relax or opts.full):
        files_are_similar = podiff.check_files_common_base(list_orig_entries,
                                                           list_new_entries)
        # and if they indeed are dissimilar, give and error
        if not files_are_similar:
            print errors['3']
            sys.exit(3)

    if opts.relax or opts.full:
        podiff.diff_files_relaxed(list_orig_entries, list_new_entries,\
                                      opts.full)
    else:
        podiff.diff_files_unrelaxed(list_orig_entries, list_new_entries)

    return
  
#################################
if __name__ == '__main__':
    main()
