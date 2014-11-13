#!/usr/bin/env python
"""
popatch -- A gettext patch module in Python
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
import sys
from StringIO import StringIO
from optparse import OptionParser
from pyg3t import gtparse, __version__
from pyg3t.util import pyg3tmain, Encoder


class PoPatch:
    """PoPatch contains methods for patching a podiff into a pofile or to
    out the new or old versions of the content in a podiff."""

    def __init__(self):
        pass

    def version_of_podiff(self, fileobject, out, new=True):
        """Extract either the new or the old version from a podiff.

        Argument:
        fileobject     file object to the diff file

        Keywork arguments:
        new            boolean new or old version
        output_object  file object for the output (Defaults to self.out)

        Returns output file object if present or None
        """
        
        for line in fileobject.readlines():
            line = line.decode('utf8') # XXX utf8
            if line.startswith('\n'):
                print(line, file=out, end='')
            elif line.startswith('--') or\
                    line.startswith(' =') or\
                    line.startswith(' N') or\
                    (line.startswith('+') and not new) or\
                    (line.startswith('-') and new):
                pass
            elif line.startswith(' ') or\
                    (line.startswith('+') and new) or\
                    (line.startswith('-') and not new):
                print(line[1:], file=out, end='')
            else:
                print('The input file is not a proper podiff '
                      'file. The conflicting line is:\n' +
                      line, file=sys.stderr)
                raise SystemExit(1)

    def patch(self, old_file, diff_file, out):
        """ Patch the original file with the diff

        Arguments:
        old_file       File object to the original file
        diff_file      File object to the diff file
        out            Output file"""

        old_gt = gtparse.parse(old_file)
        new = StringIO()
        tmpnew = Encoder(new, 'utf8')
        self.version_of_podiff(diff_file, out=tmpnew)
        new.seek(0)
        new_diff_gt = gtparse.parse(new)
        new_diff_gt_dict = new_diff_gt.dict()
        new_diff_gt_keys = new_diff_gt_dict.keys()

        for element in old_gt:
            if element.key in new_diff_gt_keys:
                print(new_diff_gt_dict[element.key].rawstring(), file=out)
            else:
                print(element.rawstring(), file=out)

        for element in old_gt.obsoletes:
            print(element.rawstring(), file=out)


def __build_parser():
    """ Build the command line parser """
    description = ('Patches a podiff into the original po file or shows '
                   'either the new or old version of the strings content in '
                   'the podiff.\n'
                   )
    usage = ('%prog [OPTION...] POFILE DIFFFILE\n'
             '       %prog [OPTION...] --new|--old DIFFFILE\n\n'
             'Use - as file argument to use standard in')
    parser = OptionParser(usage=usage, description=description,
                          version=__version__)
    parser.add_option('-o', '--output',
                      help='file to send the output to, instead of '
                      'standard out')
    parser.add_option('-n', '--new', action='store_true',  # default=False,
                      help='Do not patch, but show new version of podiff')
    parser.add_option('-m', '--old', action='store_false', dest='new',
                      help='Do not patch, but show old version of podiff')
    return parser


@pyg3tmain
def main():
    """ PoPatch main function in script mode """

    option_parser = __build_parser()
    opts, args = option_parser.parse_args()

    outfile = None
    infile0 = None
    infile1 = None
    # Define file as output if given and writeable
    if opts.output is not None:
        try:
            outfile = open(opts.output, 'w')
        except IOError, err:
            print('Could not open the output file for writing.'
                  ' open() gave the following error:', file=sys.stderr)
            print(err, sys.stderr)
            raise SystemExit(3)
    else:
        outfile = sys.stdout
    
    outfile = Encoder(outfile, 'utf8')
    popatch = PoPatch()

    # Display version of podiff mode
    if opts.new is not None:
        if len(args) != 1:
            option_parser.error('with -m or -n popatch takes exactly one '
                                 'argument')
        try:
            infile0 = sys.stdin if args[0] == '-' else open(args[0])
        except IOError, err:
            print('Could not open the input file for reading.'
                  ' open() gave the following error:', file=sys.stderr)
            print(err, file=sys.stderr)
            raise SystemExit(2)

        popatch.version_of_podiff(infile0, outfile, new=opts.new)

    else:
        # Patching mode
        if len(args) != 2:
            option_parser.error('In patching mode popatch takes exactly two '
                                'arguments')
        try:
            infile0 = sys.stdin if args[0] == '-' else open(args[0])
            infile1 = sys.stdin if args[1] == '-' else open(args[1])
        except IOError, err:
            print('Could not open the input file for reading.'
                  ' open() gave the following error:', file=sys.stderr)
            print(err, file=sys.stderr)
            raise SystemExit(2)
        popatch.patch(infile0, infile1, outfile)

#    def version_of_podiff_as_msg_catalog(self, fileobject, new=True):
#        """ This function produces either the new or the old version of a
#        the podiff content and returns it as a message catalog object
#
#        Parameters:
#        fileobject     is the file object to read from
#        new            boolean new or old version
#        """
#
#        #out = StringIO.StringIO()
#        #out = self.version_of_podiff(fileobject, new=new, output_object=out)
#        #return gtparse.parse(out)
#        raise NotImplementedError()
