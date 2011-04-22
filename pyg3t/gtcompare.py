from optparse import OptionParser
from pyg3t.gtparse import parse

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
    for msg in msgs:
        if msg.untranslated:
            u += 1
        elif msg.isfuzzy:
            f += 1
        else:
            assert msg.istranslated
            t += 1
    return u, f, t


def main():
    optparser = build_parser()
    opts, args = optparser.parse_args()
    
    if len(args) != 2:
        optparser.error('Error: Requires exactly 2 files; got %d' % len(args))



    file1, file2 = args
    
    input1 = open(file1)
    input2 = open(file2)
    cat1 = parse(input1)
    cat2 = parse(input2)
    
    if cat1.encoding != cat2.encoding:
        print 'These files have encodings %s vs %s.' % (cat1.encoding,
                                                        cat2.encoding)
        parser.error('Conflicting encodings not supported yet')
    
    msgs1 = cat1.dict()
    msgs2 = cat2.dict()
    n1 = len(msgs1)
    n2 = len(msgs2)

    header1 = msgs1.pop(cat1.header.key)
    header2 = msgs2.pop(cat2.header.key)
    
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
        print 'These files have nothing at all in common.'
        raise SystemExit
    common_fraction = float(len(common)) / n1
    if common_fraction < 0.01:
        print 'These files have almost nothing in common.'
    elif common_fraction < 0.1:
        print 'These files do not have much in common.'

    if len(first_only) == 0 and len(second_only) == 0:
        assert n1 == n2
        print 'Each file contains %d msgids, and they are all identical.' % n1
        print
    else:
        if n1 != n2:
            if n1 > n2:
                print ('Total number of messages reduced by %d from %d to %d.'
                       % (n1 - n2, n1, n2))
            else:
                assert n1 < n2
                print ('Total number of messages increased by %d from %d '
                       'to %d.' % (n2 - n1, n1, n2))
            print
        else:
            print 'Both files contain %d msgids (but they differ).' % n1
            print

        if first_only:
            u, f, t = stats(msgs1[key] for key in first_only)
            print ('%d msgids removed [u:%4d, f:%4d, t:%4d].' 
                   % (len(first_only), u, f, t))
        else:
            print 'No msgids removed.'
        
        if second_only:
            u, f, t = stats(msgs2[key] for key in second_only)
            print ('%d msgids added   [u:%4d, f:%4d, t:%4d].' 
                   % (len(second_only), u, f, t))
        else:
            print 'No msgids added.'
        print '%d msgids in common.' % len(common)
        print
    
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
                print '%d messages remain %s.' % (N, d1)
            else:
                print '%d %s messages changed to %s.' % (N, d1, d2)
    
    conflicts = 0
    for key in common:
        msg1 = msgs1[key]
        msg2 = msgs2[key]
        if msg1.istranslated and msg2.istranslated:
            for str1, str2 in zip(msg1.msgstrs, msg2.msgstrs):
                if str1 != str2:
                    conflicts += 1
    print
    if conflicts:
        print 'There are %d conflicts among translated messages.' % conflicts
    else:
        print 'There are no conflicts among translated messages.'

    #def get_all_msgstrs(msgs):
    #    msgstrs = []
    #    for msg in msgs:
    #        msgstrs.extend(msg.msgstrs)
    #    return set(msgstrs)
    
    # TODO
    # Meta-info about header?
    # info about untranslated->fuzzy msgs
    # info about fuzzy-untranslated msgs
    # info about comments?

    # An option to print each groups of messages pertaining to the
    # data, e.g. to print all the conflicts, print all the common msgs, ...
