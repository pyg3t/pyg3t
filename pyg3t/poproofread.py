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
    """ This class provides the functionality for the poproofread command line
    tool
    """

    def __init__(self, input_file_name, continue_work=False,
                 output_extension='.proofread'):
        """ Initiate variables and file states """
        self.continue_work = continue_work
        self.position = None
        self.size = None
        self.input_file_name = input_file_name
        self.output_file_name = input_file_name + output_extension
        
        # Test of readablility of input file
        if not os.access(self.input_file_name, os.R_OK):
            print 'Could not read file:', self.input_file_name, '\nExiting!'
            raise SystemExit(1)

        # Check if output file already exists
        if os.access(self.output_file_name, os.F_OK):
            # Check if the output file is writeable
            if not os.access(self.output_file_name, os.W_OK):
                print 'Could not write to file:', self.output_file_name,\
                    '\nExiting!'
                raise SystemExit(1)

            # If the file already exists but we have not specifically said
            # that we want to continue the work in it, we ask
            if not self.continue_work:
                print 'The output file', self.output_file_name, 'already '\
                    'exists!\nContinue to work with this file as the '\
                    'output(y/n)? '
                char = ''
                while char not in ['y', 'n']:
                    char = self.__read_char()
                    if char == 'n':
                        raise SystemExit(1)
                    elif char == 'y':
                        self.continue_work = True
        else:
            # Check if the output could be created
            # Get the dirname of output file or '.' if current dir
            dirname = os.path.dirname(self.output_file_name) if\
                os.path.dirname(self.output_file_name) != '' else '.'
            if not (os.access(dirname, os.W_OK) and
                    os.access(dirname, os.X_OK)):
                print 'Output file:', self.output_file_name, 'cannot be '\
                    'created\nExiting!'
                raise SystemExit(1)
            
            
        # If we should continue the work, we should alos be able to read
        # the file
        if self.continue_work and not os.access(self.output_file_name, os.R_OK):
            print 'Could not read from output file:',\
                self.output_file_name, 'to continue work\nExiting!'
            raise SystemExit(1)

    def read(self):
        """ Read files """
        
        # This should no longer be necessary, since we test for readability in
        # __init__()
        try:
            with open(self.input_file_name) as f:
                content = str().join(f.readlines())
        except IOError:
            print 'Could not read file:', self.input_file_name
            raise SystemExit(1)

        # Make a list of dictionaries, taking the diff chunks by splitting
        # the file at '\n\n'
        self.chunks = [{'diff_chunk':cont, 'comment':''} for cont in
                       content.split('\n\n')]
        
        # If we are to continue old work
        if self.continue_work:
            try:
                with open(self.output_file_name) as f:
                    content = str().join(f.readlines())
            except IOError:
                print 'Could not read file:', self.output_file_name
                raise SystemExit(1)
            
            # Split the content at '\n\n'
            self.already_done = content.split('\n\n')
            
            # Make a list of just the diff chunks
            diff_chunks = [e['diff_chunk'] for e in self.chunks]
            last_diff = ''
            gathering_comment = ''
            
            for e in self.already_done:
                # If the current chunk is a diff chunk ..
                if e in diff_chunks:
                    # .. not the first one ..
                    if last_diff != '':
                        # .. put the gathered comment in the apropriate
                        # dictionary
                        self.chunks[diff_chunks.index(last_diff)]['comment'] =\
                            gathering_comment
                    # Replace the last diff and reset the gathered comment
                    last_diff = e
                    gathering_comment = ''
                else:
                    # If the chunk was not a diff chunk, add it to the
                    # gathering comment
                    if gathering_comment == '':
                        gathering_comment = e
                    else:
                        gathering_comment += ('\n\n' + e)

            # Make sure we write the last comment even though we do not
            # encounter another real diff chunk after that
            if last_diff != '':
                self.chunks[diff_chunks.index(last_diff)]['comment'] =\
                    gathering_comment

        # After having read the files, set the position and the size
        self.position = 0
        self.size = len(self.chunks)

    def proofread(self):
        """ Proofread """
        c = ''
        # This loop is what keeps running as long as you are moving though the
        # file or editing
        while c != 'q':
            self.__print_header()

            # Read control character
            c = self.__read_char()

            # Go to next diff chunk
            if c == 'n':
                self.position += 1
                if self.position >= self.size:
                    self.position -= 1

            # Go to previous diff chunk
            if c == 'p':
                self.position -= 1
                if self.position < 0:
                    self.position += 1

            # Go to numbered diff chunk
            if c == 'g':
                self.__print_header('GOTO')
                entry = raw_input('Goto number diff: ')
                # Turn the input into an int and make sure it is within range
                try:
                    entry = int(entry)
                    assert(entry > 0 and entry <= self.size)
                    self.position = entry - 1
                except (ValueError, AssertionError):
                    print ('Error: %s is not a valid message number\n'
                           'Valid number are between 1 and %i\n\n'
                           'Press a key to continue'
                           % (str(entry), self.size))
                    self.__read_char()

            # Edit comment for diff chunk
            if c == 'e':
                self.__print_header('EDIT')
                user_input = ''

                while not (len(user_input) > 1 and user_input[-2:] == '\n\n'):
                    entry = raw_input()
                    user_input += entry + '\n'
                
                self.chunks[self.position]['comment'] = user_input[:-2]

                # Write to file everytime we have added a comment, to make sure
                # we do not loose work if the program breaks
                self.write()

    def write(self):
        """ Write to file """

        # First check whether there is actually anything to write
        if [e['comment'] for e in self.chunks].count('') == self.size:
            return False
        
        # Open output file or use stdout if none is provided
        # NOTE right now it is not possible to write to stdout
        if self.output_file_name:
            f = open(self.output_file_name, 'w')
        else:
            f = sys.stdout
        
        # Write the comments
        first = True
        for chunk in self.chunks:
            if chunk['comment'] != '':
                if not first:
                    f.write('\n\n')
                else:
                    first = False
                f.write(chunk['diff_chunk'])
                f.write('\n\n')
                f.write(chunk['comment'])

        if self.output_file_name:
            f.close()

        return True

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
        print  ('# Press (n)ext, (p)revious, (e)dit, (g)o'
                'to or (q)uit and save             '+state+' #\n'
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
    parser.add_argument('-c', '--continue_work',
                        help=('continue working on the _poproofread file that '
                              'matches the input file name'),
                        action = 'store_true', default = False)
    # Add extension option

    args = parser.parse_args()

    if args.input == None:
        print 'Argument \'input\' is mandatory'
        raise SystemExit(1)
        
    
    ppr = PoProofRead(args.input, continue_work=args.continue_work)

    ppr.read()
    ppr.proofread()
    ppr.write()
