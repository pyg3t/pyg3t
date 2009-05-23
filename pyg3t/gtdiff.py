#!/usr/bin/env python
"""
gtdiff -- A gettext diff module in Python
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

gtdiff whiteboard

Succes criteria:
================
ignore false diff by default
use python difflib
 allow for custom diff output format
allow for files with different base, i.e. diff against newer version
  via relax option
multiple file diff
allow for definition of output file
 check that it is not the same as one of the input files


Implementation:
===============
"""

import sys
from optparse import OptionParser
from pyg3t.gtparse import Parser

def build_parser():
    description = ('Prints the difference between two po-FILES in chunks'
                   'of diff output that pertain to one original string')

    usage = '%prog [OPTIONS] ORIGINAL_FILE UPDATED_FILE'
    parser = OptionParser(usage=usage, description=description)

    parser.add_option('-r', '--relax', action='store_true', default=False,
                      help='allows for files with different base, i.e. '
                      'where the msgids are not pairwise the same')
    parser.add_option('-o', '--output-file',
                      help='file to send the diff output to, instead of '
                      'standard out')
    return parser



def main():
    """The main class loads the files and output the diff
    """

    parser = build_parser()
    opts, args = parser.parse_args()

    # We need exactly two files to proceed
    if len(args) != 2:
        # System exit with error code
        print('gtdiff takes exactly two arguments')
        # FIXME handle exit codes properly
        sys.exit(1)

    print(opts.output_file)

    if opts.output_file != None:
        if (opts.output_file == args[0]) or (opts.output_file == args[1]):
            print('You don\'t really mean to send the output to '
                  'one of the input files do you')
            # FIXME handle exit codes properly
            sys.exit(2)
        

    # Load files
    parser = Parser()
    original_entries = parser.parse_asciilike(open(args[0]))
    new_entries = parser.parse_asciilike(open(args[1]))

    #for entry in original_entries:
    #    print(entry.tostring().encode('UTF-8'))

    return

    
              
              
if __name__ == '__main__':
    main()


