from optparse import OptionParser
from pyg3t.gtparse import parse

def build_parser():
    usage = '%prog [OPTIONS] FILE1 FILE2'
    description = ('Print a description of the differences between FILE1 '
                   'and FILE2')
    parser = OptionParser(usage=usage,
                          description=description)
    
    return parser


def main():
    optparser = build_parser()
    opts, args = optparser.parse_args()
    
    if len(args) != 2:
        optparser.error('Error: Requires exactly 2 files; got %d' % len(args))



    file1, file2 = args
    
    input1 = open(file1)
    input2 = open(file2)
    
    # XXXXXXXXXXXXXXX
    cat1 = parse(input1)
    cat2 = parse(input2)
    msgs1 = cat1.dict()
    msgs2 = cat2.dict()
    
    def compare_msgids(source, dest):
        missing = []
        for key in source:
            if not key in dest:
                missing.append(source[key])
        return missing

    first_only = compare_msgids(msgs1, msgs2)
    second_only = compare_msgids(msgs2, msgs1)

    
    n1 = len(msgs1)
    n2 = len(msgs2)

    if n1 != n2:
        print '%s contains %d msgids' % (file1, n1)
        print '%s contains %d msgids' % (file2, n2)
    
    if first_only:
        print '%s contains %d msgids not in %s' % (file1, len(first_only), 
                                                   file2)
    if second_only:
        print '%s contains %d msgids not in %s' % (file2, len(second_only), 
                                                   file1)
    if not (first_only or second_only):
        print 'These files contain the same msgids'
