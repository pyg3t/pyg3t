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
import StringIO
from optparse import OptionParser
from pyg3t import __version__, gtparse

class PoPatch:
    """ PoPatch contains methods for patching a podiff into a pofile or to
    out the new or old versions of the content in a podiff
    """

    def __init__(self, out=None):
        """ Initialize variables """
        self.out = out if out is not None else sys.stdout

    def version_of_podiff(self, fileobject, new=True, output_object=None):
        """ This function produces either the new or the old version of a
        the podiff content.

        Parameters:
        fileobject     is the file object to read from
        new            boolean new or old version
        """
        out = output_object if output_object is not None else self.out
        
        for line in fileobject.readlines():
            if line.startswith('\n'):
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

    def version_of_podiff_as_msg_catalog(self, fileobject, new=True):
        """ This function produces either the new or the old version of a
        the podiff content and returns it as a message catalog object

        Parameters:
        fileobject     is the file object to read from
        new            boolean new or old version
        """

        #out = StringIO.StringIO()
        #out = self.version_of_podiff(fileobject, new=new, output_object=out)
        #return gtparse.parse(out)
        raise NotImplementedError()

def __build_parser():
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
    parser.add_option('-n', '--new', action='store_true', #default=False,
                      help='Do not patch, but show new version of podiff')
    parser.add_option('-m', '--old', action='store_false', dest='new',
                      help='Do not patch, but show old version of podiff')

    return parser

def main():
    """ PoPatch main function in script mode """
    
    option_parser = __build_parser()
    opts, args = option_parser.parse_args()

    # Define file as output if given and writeable
    if opts.output is not None:
        try:
            popatch = PoPatch(open(opts.output, 'w'))
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
            fileobject = sys.stdin if args[0] == '-' else open(args[0])
        except IOError, err:
            print >> sys.stderr, ('Could not open the input file for reading.'
                                  ' open() gave the following error:')
            print >> sys.stderr, err
            raise SystemExit(2)

        popatch.version_of_podiff(fileobject, new=opts.new)

    else:
        # Patching mode
        if len(args) != 2:
            option_parser.error('In patching mode popatch takes exactly two '
                             'arguments')
        print 'Sorry, patching mode is not yet implemented'

if __name__ == '__main__':
    main()
