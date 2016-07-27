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
from optparse import OptionParser
from pyg3t import gtparse, __version__
from pyg3t.util import pyg3tmain, get_bytes_input, get_bytes_output, \
    get_encoded_output, PoError


def split_diff_as_bytes(fd):
    old = []
    new = []
    for lineno, line in enumerate(fd):
        if line.startswith(b'--- Line'):
            newline = b'\n'
            new.append(newline)
            old.append(newline)
            continue
        if line.startswith(b' ======='):
            break  # Reached summary

        token = line[:1]
        remainder = line[1:]
        if token == b' ' or token == b'\n':
            old.append(remainder)
            new.append(remainder)
        elif token == b'-':
            old.append(remainder)
        elif token == b'+':
            new.append(remainder)
        else:
            raise PoError('bad-diff-syntax',
                          'Unrecognized diff content\n'
                          'in file "%s", line %d:\n%s'
                          % (gtparse.getfilename(fd), lineno, line))
    return old, new


class PoPatch:
    """PoPatch contains methods for patching a podiff into a pofile or to
    out the new or old versions of the content in a podiff."""

    def __init__(self):
        pass

    def iterpatch(self, incat, diff_file):
        """ Patch the original file with the diff

        Arguments:
        incat          File object to the original file
        diff_file      File object to the diff file
        out            Output file"""

        old, new = split_diff_as_bytes(diff_file)
        new_diff_cat = gtparse.parse(iter(new))
        new_diff_cat_dict = new_diff_cat.dict()
        new_diff_cat_keys = new_diff_cat_dict.keys()

        for msg in incat:
            if msg.key in new_diff_cat_keys:
                yield new_diff_cat_dict[msg.key]
            else:
                yield msg

        for msg in incat.obsoletes:
            yield msg

    def writepatch(self, incat, diff_file, out):
        for msg in self.iterpatch(incat, diff_file):
            print(msg.rawstring(), file=out)

    # XXX untested
    #def patch(self, incat, diff_file):
    #    return Catalog(self.iterpatch(incat, diff_file))


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
    parser.add_option('-o', '--output', default='-',
                      help='file to send the output to, instead of '
                      'standard out')
    parser.add_option('-n', '--new', action='store_true',  # default=False,
                      help='Do not patch, but show new version of podiff')
    parser.add_option('-m', '--old', action='store_false', dest='new',
                      help='Do not patch, but show old version of podiff')
    return parser


@pyg3tmain(__build_parser)
def main(option_parser):
    """ PoPatch main function in script mode """

    opts, args = option_parser.parse_args()

    # Display version of podiff mode
    if opts.new is not None:
        if len(args) != 1:
            option_parser.error('with -m or -n popatch takes exactly one '
                                'argument')
        inbytes = get_bytes_input(args[0])
        old, new = split_diff_as_bytes(inbytes)
        lines = new if opts.new else old
        outbytes = get_bytes_output(opts.output)
        for line in lines:
            outbytes.write(line)
    else:
        # Patching mode
        if len(args) != 2:
            option_parser.error('In patching mode popatch takes exactly two '
                                'arguments')

        incat_file = get_bytes_input(args[0])
        incat = gtparse.parse(incat_file)

        diff_file = get_bytes_input(args[1])
        outcat_file = get_encoded_output(incat.encoding, opts.output)

        popatch = PoPatch()
        popatch.writepatch(incat, diff_file, outcat_file)
