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

import sys
from StringIO import StringIO
from optparse import OptionParser
from pyg3t import gtparse, __version__
from pyg3t.util import pyg3tmain

class PoPatch:
    """ PoPatch contains methods for patching a podiff into a pofile or to
    out the new or old versions of the content in a podiff
    """

    def __init__(self, out=None):
        """ Initialize variables

        Keyword argument:
        out            output file object
        """
        self.out = out if out is not None else sys.stdout

    def version_of_podiff(self, fileobject, new=True, output_object=None):
        """ This function produces either the new or the old version of a
        the podiff content.

        Argument:
        fileobject     file object to the diff file

        Keywork arguments:
        new            boolean new or old version
        output_object  file object for the output (Defaults to self.out)

        Returns output file object if present or None
        """
        out = output_object if output_object is not None else self.out

        for line in fileobject.readlines():
            if line.startswith('\n'):
                #out.write()
                print >> out, line,
            elif line.startswith('--') or\
                    line.startswith(' =') or\
                    line.startswith(' N') or\
                    (line.startswith('+') and not new) or\
                    (line.startswith('-') and new):
                pass
            elif line.startswith(' ') or\
                    (line.startswith('+') and new) or\
                    (line.startswith('-') and not new):
                print >> out, line[1:],
            else:
                print >> sys.stderr, ('The input file is not a proper podiff '
                                      'file. The conflicting line is:\n' +
                                      line)
                raise SystemExit(1)

        return out if output_object is not None else None

    def patch(self, old_file, diff_file, output_object=None):
        """ Patch the original file with the diff

        Arguments:
        old_file       File object to the original file
        diff_file      File object to the diff file

        Keyword argument:
        output_object  file object for the output (Defaults to self.out)

        Returns output file object if present or None
        """
        out = output_object if output_object is not None else self.out

        old_gt = gtparse.parse(old_file)
        new = self.version_of_podiff(diff_file, output_object=StringIO())
        new.seek(0)
        new_diff_gt = gtparse.parse(new)
        new_diff_gt_dict = new_diff_gt.dict()
        new_diff_gt_keys = new_diff_gt_dict.keys()

        for element in old_gt:
            if element.key in new_diff_gt_keys:
                print >> out, new_diff_gt_dict[element.key].rawstring()
            else:
                print >> out, element.rawstring()

        for element in old_gt.obsoletes:
            print >> out, element.rawstring()

        return out if output_object is not None else None


def __build_parser():
    """ Build the command line parser """
    description = ('Patches a podiff into the original po file or shows '
                   'either the new or old version of the strings content in '
                   'the podiff.\n'
                   '\n'
                   'NOTE: Patching is not yet implemented'
                   )

    usage = ('%prog [OPTIONS] [ORIGINAL_FILE] PODIFF_FILE\n\n'
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
            popatch = PoPatch(outfile)
        except IOError, err:
            print >> sys.stderr, ('Could not open the output file for writing.'
                                  ' open() gave the following error:')
            print >> sys.stderr, err
            raise SystemExit(3)
    else:
        popatch = PoPatch()

    # Display version of podiff mode
    if opts.new is not None:
        if len(args) != 1:
            option_parser.error('with -m or -n popatch takes exactly one '
                                 'argument')
        try:
            infile0 = sys.stdin if args[0] == '-' else open(args[0])
        except IOError, err:
            print >> sys.stderr, ('Could not open the input file for reading.'
                                  ' open() gave the following error:')
            print >> sys.stderr, err
            raise SystemExit(2)

        popatch.version_of_podiff(infile0, new=opts.new)

    else:
        # Patching mode
        if len(args) != 2:
            option_parser.error('In patching mode popatch takes exactly two '
                             'arguments')
        try:
            infile0 = sys.stdin if args[0] == '-' else open(args[0])
            infile1 = sys.stdin if args[1] == '-' else open(args[1])
        except IOError, err:
            print >> sys.stderr, ('Could not open the input file for reading.'
                                  ' open() gave the following error:')
            print >> sys.stderr, err
            raise SystemExit(2)
        popatch.patch(old_file=infile0, diff_file=infile1)

    # Clean up, close files
    if outfile is not None:
        outfile.close()
    for infile in [infile0, infile1]:
        if infile not in [None, sys.stdin]:
            infile.close()

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
