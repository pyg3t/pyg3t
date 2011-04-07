#!/usr/bin/env python

"""
poproofread -- A podiff proofreader for the terminal
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

import argparse
import sys, tty, termios
import os

class PoProofRead():

    def __init__(self, input_file_name, output_file_name = None):
        self.input_file_name = input_file_name
        self.output_file_name = output_file_name

    def read(self):
        try:
            with open(self.input_file_name) as f:
                content = str().join(f.readlines())
        except IOError:
            print 'Could not read file:', self.input_file_name
            raise SystemExit(1)

        self.chunks = [{'diff_chunk':cont, 'comment':''} for cont in
                       content.split('\n\n')]
        self.position = 0
        self.size = len(self.chunks)

    def proofread(self):
        c = ''
        while c != 'q':
            self.__print_header()

            # Read control character
            c = self.__read_char()

            if c == 'n':
                self.position += 1
                if self.position >= self.size:
                    self.position -= 1

            if c == 'p':
                self.position -= 1
                if self.position < 0:
                    self.position += 1

            if c == 'e':
                self.__print_header('EDIT')
                user_input = ''

                while not (len(user_input) > 1 and user_input[-2:] == '\n\n'):
                    entry = raw_input()
                    user_input += entry + '\n'
                
                self.chunks[self.position]['comment'] = user_input[:-2]

    def write(self):
        if self.output_file_name:
            f = open(self.output_file_name, 'w')
        else:
            f = sys.stdout
        
        for chunk in self.chunks:
            if chunk['comment'] != '':
                f.write(chunk['diff_chunk'])
                f.write('\n\n')
                f.write(chunk['comment'])
                f.write('\n\n')

        if self.output_file_name:
            f.close()

    def __read_char(self):
        """ Recipe for reading single char, without pressing enter at the end
        from http://code.activestate.com/recipes/134892-getch-like-unbuffered
        -character-reading-from-stdin/
        """
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    def __print_header(self, state = '    '):
        # Clear terminal
        os.system( [ 'clear', 'cls' ][ os.name == 'nt' ] )
        # Print header
        print ('########################################'
               '########################################')
        status_length = len(str(self.position+1)) + len(str(self.size)) + 4
        print '# poproofread', (78-status_length-13-2)*' ',\
            str(self.position+1),'of', str(self.size) + ' #'
        print  ('# Press (n)ext, (p)revious, (e)dit or (q'
                ')uit and save                     '+state+' #\n'
                '########################################'
                '########################################')
        # Print diff chunk
        print self.chunks[self.position]['diff_chunk']
        print ('########################################'
               '########################################')
        if state != 'edit' and self.chunks[self.position]['comment'] != '':
            print self.chunks[self.position]['comment']

if __name__ == "__main__":
    parser = argparse.ArgumentParser(\
        description='Proofread podiffs. WARNING WARNING WARNING poproofread is '
        'in very early stage of developement. Expect frequent brackages')
    parser.add_argument('input',
                        help='input filename')
    parser.add_argument('-o', '--output',
                        help='output filename')

    args = parser.parse_args()

    if args.input == None:
        print 'Argument \'input\' is required'
        
    
    ppr = PoProofRead(args.input, args.output)

    ppr.read()
    ppr.proofread()
    ppr.write()
