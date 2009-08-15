#!/usr/bin/env python

# +--------------------------------------------------------------+
# | This is the old podiff, which is to be replaced by a version |
# | using the centralized parser as well as difflib              |
# +--------------------------------------------------------------+

# Import statements
import sys, getopt, commands

# Exit statuses and error messages
ERROR=[]
ERROR.append('')
ERROR.append('Unknown command line option')                # Error status 1
ERROR.append('Incorrect number of command line arguments') # Error status 2
ERROR.append('The systems diff-command returned an error') # Error status 3
ERROR.append('Files are the same')                         # Error status 4

VERSION='0.21beta'

# Large strings
USAGE=''\
       'USAGE: podiff [OPTIONS] old.po new.po\n'\
       '\n'\
       'Command line options:\n'\
       '-e\tenables E3C(Excessively Eager Editor Compensation)\n'\
       '-h\tto get help\n'\
       '-v\tprints the version number\n'\
       '\n'\
       'This is the podiff script. Version ' + VERSION + '\n'\
       'The podiff script is designed to generate diffs of .po(gettext) files that\n'\
       'always contains the amount of context that pertains to the changed string,\n'\
       'instead of a fixed amount as you get with diff -u\n'\
       '\n'\
       'Written by Kenneth Nielsen k.nielsen81@gmail.com   Feb 19, 2007\n'\
       'If the script generates an error, then please send me an e-mail and attach\n'\
       'both the output and the .po-files.'

USAGE_SHORT='USAGE: podiff [OPTIONS] old.po new.po\n'\
             '\n'\
             'Command line options:\n'\
             '-h\tto get help\n'\
             '-v\tprints the version number\n'\
             '-e\tenables E3C(Excessively Eager Editor Compensation)'

CHANGELOG=''\
           'version 0.21beta\n'\
           'Fixed split if there is space at ending of line in comments'



"""
Prints an exit-message and exits
"""
def Exit(exit_status):
    if exit_status > 0:
        sys.exit(ERROR[exit_status])
    else:
        sys.exit()
            
"""
Splits the file into messages. Cuts of the first lines of diff syntax and obsolete
messages and then calls GetRealDiff to get the diff analyzed and possible cleaned
up
"""
def ParseDiff(diff):

    lines = diff.splitlines(1)
    old_point=0
    line_num=0

    # Finds the first line containung obsolete messages
    for line in lines:
        if line.count('#~') and old_point==0:
            old_point=line_num
        line_num=line_num + 1

    if old_point==0:
       old_point=len(lines)

    # Cuts of first three lines of diff syntax and obsolete messages in the end, if any
    diff_cut=''
    for n in range(3,old_point):
        diff_cut = diff_cut + lines[n]
            
    # Splits diff by newlines
    chunks = diff_cut.split('\n \n')

    for n in range(len(chunks)-1):
        chunks[n]=chunks[n] + '\n'

    # Adds the chunks that contain diff to chunks_with_diff
    chunks_with_diff=[]    
    for chunk in chunks:
        diff_lines=0
        for lines_in_chunk in chunk.splitlines(1):
            if lines_in_chunk[0] in '+-':
                diff_lines=diff_lines+1

        if diff_lines > 0:
            chunks_with_diff.append(chunk)

    # Even if E3C is not activated, the GetRealDiff is still called to analyze the diff
    # but the new diff is then overwritten with the old one and returned along with the stats
    messages, stats = GetRealDiff(chunks_with_diff)

    if not E3C:
        messages = chunks_with_diff
        
    return messages, stats

"""
Gathers statistics about the state of the different chunks. And cleans them up is necessary.
Uses RebuildMessages get the original messages and have them analyzed.
"""
def GetRealDiff(chunks_with_diff):
    """
    stats=
    [0.number of fake diffchunks,
     1.number of nice diff,
     2.number of nice fuzzy,
     3.number of UGLY diff,
     4.number of UGLY fuzzy,
     5.number of diffchunks]
    """
    stats=[0,0,0,0,0,0]
    readable_diff=[]
    for chunk in chunks_with_diff:
        stats[5] = stats[5] + 1
        old, new, pertaining_diff, diffstate = RebuildMessages(chunk)

        # State 0 we don't want in readbale_diff at all
        if diffstate == 0:
            stats[0] = stats[0] + 1
        # States 1 and 2 can be added without any trouble because they are already nice
        if diffstate in [1,2]:
            if diffstate == 1:
                stats[1] = stats[1] + 1
            else:
                stats[2] = stats[2] + 1
            readable_diff.append(chunk)
        # States 3 and 4 require manual reconstruction in order for it to be readable
        if diffstate in [3,4]:
            if diffstate == 3:
                stats[3] = stats[3] + 1
            else:
                stats[4] = stats[4] + 1
            """
            types of chunk content, numbers used in new and pertaining_diff
            0 is #  translator comment
            1 is #. developer comment
            2 is #: file-reference
            3 is #, code-style, fuzzy
            4 is msgid
            5 is msgstr
            """
            tmp_str = pertaining_diff[0]
            tmp_str = tmp_str + AddWithSpaceInfront(new[1])
            tmp_str = tmp_str + AddWithSpaceInfront(new[2])
            tmp_str = tmp_str + pertaining_diff[3]
            tmp_str = tmp_str + AddWithSpaceInfront(new[4])
            tmp_str = tmp_str + pertaining_diff[5]
            readable_diff.append(tmp_str)            
     
    return readable_diff, stats

"""
Add a space in front of all lines in the chunk (to emulate un-changed diff)
"""
def AddWithSpaceInfront(string):
    str=''
    for line in string.splitlines(1):
        str = str + ' ' + line

    return str


def RebuildMessages(chunk):
    """
    types of chunk content
    0 is # 
    1 is #.
    2 is #:
    3 is #,
    4 is msgid
    5 is msgstr
    """
    old=['','','','','',''];new=['','','','','','']
    old_string=['','','','','',''];new_string=['','','','','','']
    pertaining_diff=['','','','','','']
    state=-1

    # Determines the type(state) of the current line
    for line in chunk.splitlines(1):
        idline=False
        plural=False

        # Comments
        if line[1] == '#':
            if line[1:3] == '# ':
                state=0
            if line[1:3] == '#.':
                state=1
            if line[1:3] == '#:':
                state=2
            if line[1:3] == '#,':
                state=3

        # Messages
        if line[1] == 'm':
            if line[1:6] == 'msgid':
                state=4
                idline=True
                if line[1:13] == 'msgid_plural':
                    plural = True
            if line[1:6] == 'msgst':
                state=5
                idline=True
                if line[1:8] == 'msgstr[':
                    plural = True

        if state == -1:
            print 'state not set, THIS SHOULD NOT HAPPEN'

        # Collects the pertaining diff sorted by type
        pertaining_diff[state]=pertaining_diff[state] + line
        
        # Rebuilds old and new messages, and create a one line version for wasy comparison
        # States 0-3
        if state in [0,1,2,3]:
            if line[0] == ' ':
                old[state] = old[state] + line[1:]
                old_string[state] = old_string[state] + line[3:-1]
                new[state] = new[state] + line[1:]
                new_string[state] = new_string[state] + line[3:-1]
            if line[0] == '-':
                old[state] = old[state] + line[1:]
                old_string[state] = old_string[state] + line[3:-1]
            if line[0] == '+':
                new[state] = new[state] + line[1:]
                new_string[state] = new_string[state] + line[3:-1]

        # States 4 and 5. Note here we have to distinguish between ordinary lines, idlines and
        # plural idlines
        if state in [4,5]:
            if line[0] == ' ':
                old[state] = old[state] + line[1:]
                new[state] = new[state] + line[1:]
                if idline:
                    if state == 4:
                        if plural:
                            old_string[state] = old_string[state] + line[15:-2]
                            new_string[state] = new_string[state] + line[15:-2]
                        else:
                            old_string[state] = old_string[state] + line[8:-2]
                            new_string[state] = new_string[state] + line[8:-2]
                    else:
                        if plural:
                            old_string[state] = old_string[state] + line[12:-2]
                            new_string[state] = new_string[state] + line[12:-2]
                        else:
                            old_string[state] = old_string[state] + line[9:-2]
                            new_string[state] = new_string[state] + line[9:-2]
                else:
                    old_string[state] = old_string[state] + line[2:-2]
                    new_string[state] = new_string[state] + line[2:-2]
                    
                        
            if line[0] == '-':
                old[state] = old[state] + line[1:]
                if idline:
                    if state == 4:
                        if plural:
                            old_string[state] = old_string[state] + line[15:-2]
                        else:
                            old_string[state] = old_string[state] + line[8:-2]
                    else:
                        if plural:
                            old_string[state] = old_string[state] + line[12:-2]
                        else:
                            old_string[state] = old_string[state] + line[9:-2]
                else:
                    old_string[state] = old_string[state] + line[2:-2]

            if line[0] == '+':
                new[state] = new[state] + line[1:]
                if idline:
                    if state == 4:
                        if plural:
                            new_string[state] = new_string[state] + line[15:-2]
                        else:
                            new_string[state] = new_string[state] + line[8:-2]
                    else:
                        if plural:
                            new_string[state] = new_string[state] + line[12:-2]
                        else:
                            new_string[state] = new_string[state] + line[9:-2]
                else:
                    new_string[state] = new_string[state] + line[2:-2]
                    
                        
    # Now it's time for the comparison
    diffstate=0
    # 0 is no diff
    # 1 is diff
    # 2 is diff, fuzzy
    # 3 is diff BUT UGLY DIFF
    # 4 is diff, fuzzy but BUT UGLY DIFF

    # If there actually is a difference in any of the types that the translator is allowed to change (strings)
    # the diffstate is set to 1
    if (old_string[0] != new_string[0]) or (old_string[3] != new_string[3]) or (old_string[5] != new_string[5]):
        diffstate=1
        # If there is a diffence in the code-style, fuzzy it is set to fuzzy (string)
        if old_string[3] != new_string[3]:
            diffstate=2
        # If there is a difference in any of the types that the translator aren't allowed to change (orig po content)
        # the there is added 2 to the state to show that it is a UGLY diff
        if (old[1] != new[1]) or (old[2] != new[2]) or (old[4] != new[4]):
            diffstate=diffstate+2
     
    return old, new, pertaining_diff, diffstate
    
"""
Main method. Parses commandline arguments. Gets commandlins-type diff. Calls for evaluation of this diff.
Prints the output..
"""
def main():
    # A boolean E3C is made global and intialized
    # E3C stands for Excessively Eager Editor Compensation
    global E3C
    E3C=False

    # Parse command line options
    try:
        opt_list, arg_list = getopt.getopt(sys.argv[1:], 'hve')
        """
        Put : after an option to make it take a value like 'hv:'
        The try statement is there to capture the error that is thrown if an
        unknown command-line option is used
        """
    except getopt.GetoptError:
        print USAGE_SHORT
        Exit(1)
        
    for opt in opt_list:
        """
        Parses through the command-line options. I suppose it should be made as a
        case statement if there are any more options
        It says opt[0] because opt[1] can be the option value
        """
        if opt[0] == '-h':
            print USAGE
            Exit(0)
        if opt[0] == '-v':
            print 'Version: ' + VERSION
            Exit(0)
        if opt[0] == '-e':
            E3C=True
                    
    
    # Checks if there are exactly 2 arguments
    if len(arg_list) != 2:
        print USAGE_SHORT
        Exit(2)
                        

    """
    Get systems diff output. It is executed so that it will provide 100000 lines of
    context, that should be enough to ensure us to get the entire file as context
    no-matter what. It is executed with \" around the files to ensure that spaces in
    file-names passes through without any trouble
    """
    diff_status, diff=commands.getstatusoutput('diff -U 1000000 \"' + arg_list[0] + '\" \"' + arg_list[1] + '\"')
                        
    """
    Here we look at the exit status of the diff command. Now for what ever reason
    the systems diff command returns 0 if there is no difference and 1 is there is
    and something else if there is an error. But these are translated by
    commands.getstatusoutput so that 0 is 0 but 1 becomes 256. So first I check if
    the exits status is different from that, which means that it actually returns
    a diff. If so, if it es empty I respond to that, and otherwise I tell the user
    that diff returned an error, prints the error and exits
    """
    if diff_status != 256:
        if diff_status == 0:
            Exit(4)
        else:
            print 'The diff command returned an error. This is the output:'
            print '\n' + diff
            Exit(3)



    # Parse the diff
    messages, stats = ParseDiff(diff)

    # Output added to string for easier implementation of write-to-file functionality
    output_string='\n'.join(messages)


    """
    stats=
    [0.number of fake diffchunks,
     1.number of nice diff,
     2.number of nice fuzzy,
     3.number of UGLY diff,
     4.number of UGLY fuzzy,
     5.number of diffchunks]
    """
    if E3C:
        status_string=''\
                       ' ===============================================================================\n'\
                       ' Diff created and cleaned up                                                    \n'\
                       ' ---------------------------                                                    \n'\
                       ' Total number of messages minus fake ones equals total number of real messages. \n'\
                       ' ' + str(stats[5]) + ' - ' + str(stats[0]) + ' = ' + str(stats[5] - stats[0]) + '\n'\
                       '                                                                                \n'\
                       ' Messages that did not need clean up: Changed: ' + str(stats[1]) + '            \n'\
                       '                                    : Fuzzy  : ' + str(stats[2]) + '            \n'\
                       ' Messages that did was cleaned up   : Changed: ' + str(stats[3]) + '            \n'\
                       '                                    : Fuzzy  : ' + str(stats[4]) + '            \n'\
                       '                                             : ---------------------------------\n'\
                       '                                      Total  : ' + str(sum(stats[1:5])) + '     \n'\
                       ' ===============================================================================\n'
    else:
        status_string=''\
                       ' ===============================================================================\n'\
                       ' Diff created                                                                   \n'\
                       ' Message total: ' + str(stats[5]) + '                                           \n'\
                       ' ===============================================================================\n'

    output=output_string + '\n' + status_string

    if stats[0] != 0 and not E3C:
        err_string=''\
                    ' \n'\
                    ' WARNING: podiff has detected a number of FAKE DIFF-CHUNKS in the diff. Fake\n'\
                    ' meaning, that there is no real change which has been added by you. This is most\n'\
                    ' likely because you use an editor program that likes to rearrange the reference\n'\
                    ' comments "#:" or the msgid.\n'\
                    ' \n'\
                    ' By podiff analyses, from the\n'\
                    ' ' + str(stats[5]) + ' diff-chunks, there are\n'\
                    ' ' + str(stats[0]) + ' fake diff-chunks and \n'\
                    ' ' + str(stats[3] + stats[4]) + ' diff-chunks made "messy" due to the editor-software.\n'\
                    ' \n'\
                    ' All in all by podiffs analyzes that there are a total of\n'\
                    ' ' + str(sum(stats[1:5])) + ' chunks which has actually be edited by you.\n'\
                    ' If this number seem right to you, consider running the script with the -e option.\n'\
                    ' This will enable E3C(Excessively Eager Editor Compensation) and will give you a\n'\
                    ' nice cleaned up diff.\n'
        print output
        sys.exit(err_string)

    if (stats[3] + stats[4] > 0) and not E3C:
        err_string=''\
                    ' \n'\
                    ' podiff has detected that some of the chunks you have edited contain reference\n'\
                    ' comments "#:" or msgid\'s which has been moved around. This can because you use an\n'\
                    ' editor program that likes to rearrange them. The total number of concerned messages\n'\
                    ' is ' + str(stats[3] + stats[4]) + ' . If this i more than a few messages you should\n'\
                    ' consider running podiff with the -e option. This will let it clean up the diff to\n'\
                    ' make it easier to read.\n'
        print output
        sys.exit(err_string)

    print output
                                                
if __name__ == '__main__':
    main()


# Done. You gotta love Python

