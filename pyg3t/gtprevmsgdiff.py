from __future__ import print_function
from optparse import OptionParser
from pyg3t.gtparse import parse
from pyg3t.gtdifflib import DefaultWDiffFormat, FancyWDiffFormat, diff
from pyg3t.util import pyg3tmain

@pyg3tmain
def main():
    usage = '%prog [OPTION] POFILE'
    description = 'Print wordwise diff of msgid and previous msgid ' \
        'entries in gettext message catalogs.'
    p = OptionParser(usage=usage, description=description)
    p.add_option('--fancy', action='store_true',
                 help='use colors to highlight changes')
    p.add_option('--include-translated', action='store_true',
                 help='write differences for translated messages as well')
    
    opts, args = p.parse_args()

    if opts.fancy:
        formatter = FancyWDiffFormat()
    else:
        formatter = DefaultWDiffFormat()
    
    if len(args) != 1:
        p.error('Only a single file expected; got %d' % len(args))
    cat = parse(open(args[0]))
    for msg in cat:
        if not msg.has_previous_msgid:
            continue
        if msg.istranslated and not opts.include_translated:
            continue
        
        if msg.istranslated:
            status = 'translated'
        elif msg.isfuzzy:
            status = 'fuzzy'
        else:
            status = 'untranslated'
        
        header = 'Line %d (%s)' % (msg.meta['lineno'], status)
        print(('--- %s ' % header).ljust(78, '-'))
        oldmsgid = msg.previous_msgid.replace('\\n', '\\n\n')
        newmsgid = msg.msgid.replace('\\n', '\\n\n')
        difference = diff(oldmsgid, newmsgid, formatter)
        print(difference.rstrip('\n'))
