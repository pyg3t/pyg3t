#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys, locale
import os

#locale.setlocale(locale.LC_ALL, ("en_DK", None))
#That won't work, so until it does we'll misuse UPPER and LOWER as defined below
#instead of those in the python string API
#Normally these things should be accessed from string.uppercase etc.
UPPER = 'ABCDEFGHIJKLMNOPQRSTUVWXYZÆØÅ'
LOWER = 'abcdefghijklmnopqrstuvwxyzæøå'

DOCUMENTATION='\n'\
'USAGE: poabc.py [qm] file.po\n'\
'\n'\
'poabc - PO-file Automatic Blunder Corrector v0.31 beta\n'\
'\n'\
'This utility parses a .po translation file, writing suspected errors to\n'\
'standard output.  Errors are suspected whenever inconsistences between\n'\
'msgid and msgstr are detected in terms of case or type of the leading\n'\
'characters, number or type of trailing non-alphabetic characters (such as\n'\
'punctuation) or number of hotkey assignments (underscores).\n'\
'\n'\
'Optional parameters:\n'\
'    q - warn about single quotes not converted to double quotes\n'\
'    m - also run msgmft -cv file.po (for lazy translators)\n'\
'\n'\
'Written by Ask Hjorth Larsen <asklarsen@gmail.com>\n'\
'Thanks to Kenneth Nielsen for miscellaneous programming and testing\n'\
'Mar 22, 2007.\n'

"""
-----------------------
Version history
-----------------------
v0.32
Treats carriage-return linefeed correctly.

v0.31
Supports msgctxt.

v0.3
Never complains about the msgid "translator-credits"
Optionally warns about lacking quotation mark conversion from ' to \"
Prints total warning count
Improved output format
Prints summary of warnings and string counts
Command line argument m for users who are too lazy to run msgfmt

v0.2
Prints line numbers of warnings
Warns about untranslated strings
Supports singular/plural entry syntax
Warns about unsupported syntax
Improved robustness in general

v0.1
Compare case, leading/trailing characters, whitespace
"""

#Used in place of locale-dependent string.isalpha()
def isalpha(char):
    return isupper(char) | islower(char)

#Used in place of locale-dependent string.isupper()
def isupper(char):
    return UPPER.find(char) != -1

#Used in place of locale-dependent string.islower()
def islower(char):
    return LOWER.find(char) != -1

"""
Compares the first character in each of the two specified strings and
returns False if an error is suspected, otherwise True.

An error is suspected unless one of the following is true:
    1) both strings start with an uppercase letter
    2) both strings start with a lowercase letter
    3) both strings start with the same non-alphabetic character
"""
def compareCase(msgid, msgstr):
    if msgid == '' or msgstr == '':
        return msgid == msgstr
    char1 = msgid[0]
    char2 = msgstr[0]

    returnValue = True

    #If alphabetic characters, compare case.
    if isalpha(char1) and isalpha(char2):
        bothUpper = isupper(char1) and isupper(char2)
        bothLower = islower(char1) and islower(char2)
        return bothUpper | bothLower
    else:
        #Non-alphabetic characters. These should probably be identical.

        return char1 == char2

"""
Returns a list of the lines starting with '#' beginning at the specified index
"""
def readComments(lines, index):
    startIndex = index
    maxIndex = len(lines)
    comments = []
    while (index < maxIndex) and (lines[index].startswith('#') or lines[index].isspace()):
        comments.append(lines[index])
        index += 1
    return comments, index

def readString(lines, index, qualifier):
    maxIndex = len(lines)
    relevantLines = []
    if lines[index].startswith(qualifier):
        #Remove the qualifier, add remainder to relevant lines
        #Adjust for leading quote and trailing quote/newline
        relevantLines.append(lines[index].strip()[len(qualifier)+1:-2])
        index += 1
        
        while (index < maxIndex) and lines[index].startswith('"'):
            #Also adjust for leading quote and trailing quote/newline
            relevantLines.append(lines[index].strip()[1:-2])
            index += 1
            
    string = ''.join(relevantLines)
    return (string, index)

def readPluralmsgid(lines, index):
    return readString(lines, index, 'msgid_plural ')

def readmsgctxt(lines, index):
    if lines[index].startswith('msgctxt '):
        return readString(lines, index, 'msgctxt ')
    else:
        return lines, index

def readmsgid(lines, index):
    return readString(lines, index, 'msgid ')

def readmsgstr(lines, index):
    return readString(lines, index, 'msgstr ')

def skipWhiteSpace(lines, index):
    maxIndex = len(lines)
    while (index < maxIndex) and lines[index].isspace():
        index += 1
    return index

"""
These variables are used by the readEntry function in a spaghetti-like way.
They are meant to keep track of plural forms, ensuring that they are returned
sequentially (which would be difficult to do using only one index variable).
The variables are modified on subsequent readEntry() calls
"""
pluralmsgid = None
pluralFormEntry = False
pluralFormCount = 0

"""
Takes a list of strings and a line index as parameters.
Returns a quadruple containing the list of comments, msgid, msgstr found in the
strings, along with the line index after the msgstr terminates.

Subsequent calls of this method using the returned index will return
sequential msgid-msgstr pairs.

The returned strings have newlines and quotation marks removed except those
explicitly declared in the string, and do not contain the "msgid" or "msgstr"
declarations.

Plural forms of msgstr will be returned one after another on subsequent calls,
together with the plural msgid. The singular msgstr will be returned with
the singular msgid.
"""
def readEntry(lines, index):

    global pluralmsgid, pluralFormEntry, pluralFormCount
    
    startIndex = index
    (comments,index) = readComments(lines, index)
    
    if index >= len(lines):
        #Just return None if at end of file, parsing will stop
        return (None, None,None,index)

    if pluralFormEntry:
        #Plural forms!
        #Relevant msgid stored globally from earlier invocation
        msgid = pluralmsgid
    else:
        #As long as we're not working with plural forms, we want a new msgid
        (msgctxt, index) = readmsgctxt(lines, index)
        (msgid, index) = readmsgid(lines, index)

    #Check for plural forms. Indexing is okay since file cannot end here
    if lines[index].startswith('msgid_plural'):
        pluralFormEntry = True
        singularmsgid = msgid
        (plurString, index) = readString(lines, index, 'msgid_plural ')
        pluralmsgid = plurString #Store for subsequent invocations

        (msgstr, index) = readString(lines, index, 'msgstr[0] ')
        pluralFormCount = 1
        #Now msgid and msgstr refer to singular forms, and we're done
        
    elif pluralFormEntry: #We are already working with plural forms
        #Make sure there are more plural forms
        if lines[index].startswith('msgstr['):
            msgid = pluralmsgid #stored from earlier
            (msgstr, index) = readString(lines, index, 
                                         'msgstr['+str(pluralFormCount)+'] ')
            pluralFormCount += 1
        else:
            #There are no more plural forms, so reset the variables
            pluralFormEntry = False
            pluralFormCount = 0
            pluralmsgid = None
            #Just return, the method will be invoked again and move on.
            return (None, None, None, index)
            
    else: #normal procedure - find msgstr
        (msgstr, index) = readmsgstr(lines, index)

    if startIndex == index:
        #No sensible strings were found, but we have to move on.
        #Skip to next line
        print '---Unsupported syntax, skipping line',index,'---'
        index += 1
        return (None, None, None, index)
    index = skipWhiteSpace(lines, index)
    return (comments, msgid, msgstr, index)

def stripPipeChar(msgid):
    pipeIndex = msgid.find('|')
    if pipeIndex != -1:
        return msgid[pipeIndex+1:]
    else:
        return msgid
    return msgid
    

"""
Compares the trailing characters of the two specified strings. Returns False
if an error is suspected, otherwise True.

An error is suspected unless all trailing non-alphabetic characters are
identical.
"""
def compareTrailingChars(msgid, msgstr):
    index = 0
    minIndex = - min( [len(msgid), len(msgstr)] )
    hasalpha = False
    consistent = True
    while (index > minIndex) and (not hasalpha) and consistent:
        index = index - 1
        idAlpha = isalpha(msgid[index])
        strAlpha = isalpha(msgstr[index])
        hasalpha = idAlpha or strAlpha
        consistent = ((msgid[index] == msgstr[index]) or (idAlpha and strAlpha))

    return consistent, index

"""
Compares the hotkey designations of the two specified strings.
Returns a triple consisting of the two input strings with any underscores
removed, and a boolean which is False if an error is suspected, otherwise True.

An error is suspected if and only if differing numbers of underscores occur
in the specified strings.
"""
def checkHotkeys(msgid, msgstr):
    idCount = msgid.count('_')
    strCount = msgstr.count('_')

    msgidNoKey = msgid.replace('_','')
    msgstrNoKey = msgstr.replace('_','')
    
    return msgidNoKey, msgstrNoKey, (idCount == strCount)

"""
Takes a msgid string, then replaces single quotation marks with double
quotation marks such that the trailing/leading character analysis will
not mark different use of quotation marks as an error, unless the msgstr
uses single quotation marks.
"""
def hackQuotationMarkConversion(msgid):
    return msgid.replace("'", '\\"')

def makeErrMsg(msg, index):
    return '=== Line '+str(index-1)+' : '+msg+' ==='
    
"""
Parses the given list of strings for suspected errors. The strings are assumed
to be in po-file format, each string being one line, and each string being
terminated by a newline character.

Suspected errors will be written to standard output.
"""
def parse(lines):
    maxIndex = len(lines)
    index = 0
    stringCount = 0
    #We're skipping the first string in a moment
    #However the official list of .po-files seems to do this as well, so we'll
    #avoid correcting for this uncounted string
    warningCount = 0
    fuzzy = 0
    untranslated = 0

    #REMEMBER: make sure msgid_plural is not counted to conform with
    #l10n.gnome.org
    
    #The first entry contains metadata and should not be counted
    (comments, msgid, msgstr, index) = readEntry(lines, index)

    #Now parse all the other entries until no more exist
    while index < maxIndex:
        (comments, msgid, msgstr, index) = readEntry(lines, index)

        if msgid == None or msgstr == None:
            continue #end of file or deliberately unsupported syntax

        stringCount += 1

        #Print the current string if errors are found
        printStrings = False
        
        if msgid == '':
            print makeErrMsg('Empty string for translation?', index)
            print
            warningCount += 1
            continue
        if msgstr == '':
            print makeErrMsg('Untranslated string', index)
            print msgid
            print
            untranslated += 1
            warningCount += 1
            continue
        #Special string which we should ignore
        if msgid == 'translator-credits':
            continue

        msgidNoPipe = stripPipeChar(msgid)
        if msgstr.find('|') != -1:
            print makeErrMsg('Pipe character in msgstr', index)
            printStrings = True
            warningCount += 1

        #Make sure no warnings are issued just because of bad quotation mark use
        if convertQuotes:
            msgidConvQuotes = hackQuotationMarkConversion(msgidNoPipe)
        else:
            msgidConvQuotes = msgidNoPipe
        
        #Check hotkey assignments, then remove hotkey chars to
        #make the strings parseable by the other functions
        (msgidNoKey, msgstrNoKey, hotkey) = checkHotkeys(msgidConvQuotes, msgstr)

        #Booleans indicating possible errors
        case = compareCase(msgidNoKey, msgstrNoKey)
        (punc, trailIndex) = compareTrailingChars(msgidNoKey, msgstrNoKey)

        #Check whether string is fuzzy
        for comment in comments:
            if comment.startswith('#,') and comment.find('fuzzy') != -1:
                fuzzy += 1
                print makeErrMsg('Fuzzy string', index)
                printStrings = True

        if convertQuotes:
            if msgstr.count("'") > 1:
                print makeErrMsg('Suspicious use of quotation marks', index)
                #Prevent trailing char error due to lacking quotation mark
                #conversion, since this has been accounted for by now
                #The point is that if ' is translated to ', then it is
                #considered a quotation mark error and not a trailing
                #char mismatch
                if msgstrNoKey[trailIndex] == "'":
                    punc = True
                printStrings = True
        
        if not case:
            printStrings = True
            print makeErrMsg('Leading character type or case mismatch',index)
        if not punc:
            printStrings = True
            if (msgid[-1].isspace() ^ msgstr[-1].isspace()):
                print makeErrMsg('Trailing whitespace inconsistency', index)
            else:
                print makeErrMsg('Trailing characters or punctuation mismatch',index)
        if not hotkey:
            printStrings = True
            print makeErrMsg('Hotkey assignment inconsistency', index)

        if printStrings:
            print 'msgid "'+msgid+'"'
            print 'msgstr "'+msgstr+'"'
            print
            warningCount += 1

    print '================ Summary ================'
    print 'Total string count:', stringCount
    translatedRatio = str(100 * (stringCount-fuzzy-untranslated) / stringCount)
    print 'Translated string count:',stringCount-untranslated-fuzzy,'('+translatedRatio+'%)'
    if fuzzy > 0:
        fuzzyRatio = str(100 * fuzzy / stringCount)
        print 'Fuzzy string count:', fuzzy,'('+fuzzyRatio+'%)'
    if untranslated > 0:
        untransRatio = str(100 * untranslated / stringCount)
        print 'Untranslated string count:', untranslated,'('+untransRatio+'%)'
    print 'Total warning count:', warningCount
    print '========================================='


convertQuotes = False
checkMsgfmt = False

"""
Checks that the options string contains exactly 0 or 1 of each option,
returning True if this is the case consistently, otherwise False.
"""
def checkOpts(opts):
    
    global convertQuotes, checkMsgfmt
    
    qCount = opts.count('q')
    mCount = opts.count('m')
    if qCount == 0 or qCount == 1:
        convertQuotes = bool(qCount)
    else:
        return False
    if mCount == 0 or mCount == 1:
        checkMsgfmt = bool(mCount)
    else:
        return False    
    return True

def runMsgfmt(fileName):
    command = 'msgfmt -cv '+fileName
    print 'Running command:',command
    print
    exitStatus = os.system(command)
    print
    print 'Continuing...' #We don't know whether it succeeded but whatever
    print

"""
Parses the .po-file given by the first command-line parameter for syntax
errors, or prints help if parameters are malformed or omitted
"""
def main():
    argc = len(sys.argv)
    if argc == 1 or argc > 3:
        if argc > 3:
            print 'Received too many arguments'
        print DOCUMENTATION
    else:
        fileName = sys.argv[-1]
        options = ''
        if argc == 3:
            options = sys.argv[-2]
        if not checkOpts(options):
            print 'Bad options:',options
            print DOCUMENTATION
        else:
            file = open(fileName)
            lines = file.readlines()
            if checkMsgfmt:
                runMsgfmt(fileName)
            parse(lines)

if __name__ == '__main__':
    main()
