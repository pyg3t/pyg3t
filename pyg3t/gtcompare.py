from __future__ import print_function
from optparse import OptionParser
from dateutil.parser import parse as parse_date

from pyg3t.gtparse import parse
from pyg3t.util import pyg3tmain


def build_parser():
    usage = '%prog [OPTIONS] OLD NEW'
    description = ('Print a description of the differences between OLD '
                   'and NEW')
    parser = OptionParser(usage=usage,
                          description=description)
    return parser


def stats(msgs):
    u = 0
    f = 0
    t = 0
    n = 0
    for msg in msgs:
        n += 1
        if msg.untranslated:
            u += 1
        elif msg.isfuzzy:
            f += 1
        else:
            assert msg.istranslated
            t += 1
    assert u + f + t == n
    return u, f, t

# This list is used only to impose nice ordering
known_headers = ['Project-Id-Version', 'Report-Msgid-Bugs-To',
                 'POT-Creation-Date', 'PO-Revision-Date',
                 'Last-Translator', 'Language-Team',
                 'Language', 'MIME-Version', 'Content-Type',
                 'Content-Transfer-Encoding',
                 'Plural-Forms']

def compare_headers(headers1, headers2):
    headers_to_do = set(known_headers)
    headers_done = set()
    
    for key in headers1.keys() + headers1.keys():
        headers_to_do.add(key)

    def header_done(header):
        headers_to_do.remove(header)
        headers_done.add(header)

    def get(key):
        return headers1[key], headers2[key]

    def differs(key):
        return headers1[key] != headers2[key]
    
    def check(key):
        if differs(key):
            print('Changed header %s' % key)
            print('  was: %s' % headers1[key])
            print('  now: %s' % headers2[key])

    # Special treatment for some of the most informative headers.
    # If anything goes wrong we will just defer them to later
    # (by retaining them in headers_to_do)
    try:
        check('Project-Id-Version')
    except KeyError:
        pass
    else:
        header_done('Project-Id-Version')
    
    try:
        date1, date2 = get('POT-Creation-Date')
    except KeyError:
        pass
    else:
        if date1 != date2:
            d1 = parse_date(date1)
            d2 = parse_date(date2)
            if d1 < d2:
                print('Template of second file is more recent')
            else:
                print('Template of first file is more recent')
        else:
            print('Template creation dates coincide')
        header_done('POT-Creation-Date')

    try:
        date1, date2 = get('PO-Revision-Date')
    except KeyError:
        pass
    else:
        if date1 != date2:
            d1 = parse_date(date1)
            d2 = parse_date(date2)
            if d1 < d2:
                print('Translations in second file were revised more recently')
            else:
                print('Translations in first file were revised more recently')
        else:
            print('Translation revision dates coincide')
        header_done('PO-Revision-Date')
    
    def process_header(header):
        if header in headers_done:
            return # already handled
        try:
            check(header)
        except KeyError:
            if header in headers1 and not header in headers1:
                print('Removed header %s' % ': '.join([header, 
                                                       headers1[header]]))
            elif not header in headers1 and header in headers2:
                print('Added header %s' % ': '.join([header, 
                                                     headers2[header]]))
            else:
                assert not header in headers1 and not header in headers2
        header_done(header)

    # Copy the list as process_header makes changes to the list
    for header in list(known_headers):
        process_header(header)
    
    # The remaining ones which are "unknown"
    for header in list(headers_to_do):
        process_header(header)


def compare(cat1, cat2):
    if cat1.encoding != cat2.encoding:
        print('These files have encodings %s vs %s.' % (cat1.encoding,
                                                        cat2.encoding))
        parser.error('Conflicting encodings not supported yet')
    
    compare_headers(cat1.header.meta['headers'], cat2.header.meta['headers'])
    print()

    msgs1 = cat1.dict()
    msgs2 = cat2.dict()

    msgs1.pop(cat1.header.key)
    msgs2.pop(cat2.header.key)

    # TODO
    # info about comments?
    # 
    # An option to print messages by classification,
    # e.g. to print all the conflicts, print all the common msgs, ...
    
    n1 = len(msgs1)
    n2 = len(msgs2)
    
    def compare_msgids(source, dest):
        missing = []
        for key in source:
            if not key in dest:
                missing.append(key)
        return missing

    first_only = compare_msgids(msgs1, msgs2)
    second_only = compare_msgids(msgs2, msgs1)
    common = [key for key in msgs1 if key in msgs2]

    if len(common) == 0:
        print('These files have nothing at all in common.')
        raise SystemExit
    common_fraction = float(len(common)) / n1
    if common_fraction < 0.01:
        print('These files have almost nothing in common.')
    elif common_fraction < 0.1:
        print('These files do not have much in common.')

    if len(first_only) == 0 and len(second_only) == 0:
        assert n1 == n2
        print('Each file contains %d msgids, and they are all identical.' % n1)
        print()
    else:
        if n1 != n2:
            if n1 > n2:
                print('Total number of messages reduced by %d from %d to %d.'
                      % (n1 - n2, n1, n2))
            else:
                assert n1 < n2
                print('Total number of messages increased by %d from %d '
                      'to %d.' % (n2 - n1, n1, n2))
            print()
        else:
            print('Both files contain %d msgids (but they differ).' % n1)
            print()

        if first_only:
            u, f, t = stats(msgs1[key] for key in first_only)
            print('%d msgids removed [u:%4d, f:%4d, t:%4d].' 
                  % (len(first_only), u, f, t))
        else:
            print('No msgids removed.')
        
        if second_only:
            u, f, t = stats(msgs2[key] for key in second_only)
            print('%d msgids added   [u:%4d, f:%4d, t:%4d].' 
                  % (len(second_only), u, f, t))
        else:
            print('No msgids added.')
        print('%d msgids in common.' % len(common))
        print()
    
    transitions = dict(uu=0,
                       uf=0,
                       ut=0,
                       fu=0,
                       ff=0,
                       ft=0,
                       tu=0,
                       tf=0,
                       tt=0)
    
    def getstate(msg):
        if msg.untranslated:
            return 'u'
        elif msg.isfuzzy:
            return 'f'
        else:
            assert msg.istranslated
            return 't'

    for key in common:
        msg1 = msgs1[key]
        msg2 = msgs2[key]
        
        # u -> u : nothing happened
        # u -> f : doesn't normally happen
        # u -> t : string in f1 has been translated in f2
        # f -> u : doesn't normally happen
        # f -> f : nothing happened
        # f -> t : string in f1 has been translated in f2
        # t -> u : doesn't normally happen unless f2 newer than f1
        # t -> f : doesn't normally happen unless f2 newer than f1
        # t -> t : nothing happened
        
        transition = getstate(msg1) + getstate(msg2)
        transitions[transition] += 1
        
        descriptions = dict(u='untranslated',
                            f='fuzzy',
                            t='translated')

    for s1 in 'uft':
        for s2 in 'uft':
            t = s1 + s2
            d1 = descriptions[s1]
            d2 = descriptions[s2]
            N = transitions[t]
            if s1 == s2:
                print('%d messages remain %s.' % (N, d1))
            else:
                print('%d %s messages changed to %s.' % (N, d1, d2))
    
    conflicts = 0
    for key in common:
        msg1 = msgs1[key]
        msg2 = msgs2[key]
        if msg1.istranslated and msg2.istranslated:
            for str1, str2 in zip(msg1.msgstrs, msg2.msgstrs):
                if str1 != str2:
                    conflicts += 1
    print()
    if conflicts:
        print('There are %d conflicts among translated messages.' % conflicts)
    else:
        print('There are no conflicts among translated messages.')
    

@pyg3tmain
def main():
    parser = build_parser()
    opts, args = parser.parse_args()
    
    if len(args) != 2:
        parser.error('Error: Requires exactly 2 files; got %d' % len(args))

    file1, file2 = args
    
    input1 = open(file1)
    input2 = open(file2)
    cat1 = parse(input1)
    cat2 = parse(input2)

    compare(cat1, cat2)
