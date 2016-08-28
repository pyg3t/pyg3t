from __future__ import print_function, unicode_literals
from optparse import OptionParser
from datetime import datetime

from pyg3t.gtparse import parse
from pyg3t.util import pyg3tmain, get_encoded_output


def standard_strptime(date):
    try:
        return datetime.strptime(date, '%Y-%m-%d %H:%M%z')
    except ValueError:  # XXX ignore timezone!  This is a bit buggy
        return datetime.strptime(date[:-5], '%Y-%m-%d %H:%M')


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


def compare_headers(headers1, headers2, fd):
    headers_to_do = set(known_headers)
    headers_done = set()

    for key in list(headers1.keys()) + list(headers1.keys()):
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
            print('Changed header %s' % key, file=fd)
            print('  was: %s' % headers1[key], file=fd)
            print('  now: %s' % headers2[key], file=fd)

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
            d1 = standard_strptime(date1)
            d2 = standard_strptime(date2)
            if d1 < d2:
                print('Template of second file is more recent', file=fd)
            else:
                print('Template of first file is more recent', file=fd)
        else:
            print('Template creation dates coincide', file=fd)
        header_done('POT-Creation-Date')

    try:
        date1, date2 = get('PO-Revision-Date')
    except KeyError:
        pass
    else:
        if date1 != date2:
            d1 = standard_strptime(date1)
            d2 = standard_strptime(date2)
            if d1 < d2:
                print('Translations in second file were revised more recently',
                      file=fd)
            else:
                print('Translations in first file were revised more recently',
                      file=fd)
        else:
            print('Translation revision dates coincide', file=fd)
        header_done('PO-Revision-Date')

    def process_header(header):
        if header in headers_done:
            return # already handled
        try:
            check(header)
        except KeyError:
            if header in headers1 and header not in headers2:
                print('Removed header %s' % ': '.join([header,
                                                       headers1[header]]),
                      file=fd)
            elif header in headers2 and header not in headers1:
                print('Added header %s' % ': '.join([header,
                                                     headers2[header]]),
                      file=fd)
            else:
                assert header not in headers1 and header not in headers2
        header_done(header)

    # Copy the list as process_header makes changes to the list
    for header in list(known_headers):
        process_header(header)

    # The remaining ones which are "unknown"
    for header in list(headers_to_do):
        process_header(header)


def compare(cat1, cat2, fd):
    compare_headers(cat1.headers, cat2.headers, fd)
    print(file=fd)

    msgs1 = cat1.dict()
    msgs2 = cat2.dict()

    msgs1.pop(cat1.msgs[0].key)
    msgs2.pop(cat2.msgs[0].key)

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
            if key not in dest:
                missing.append(key)
        return missing

    first_only = compare_msgids(msgs1, msgs2)
    second_only = compare_msgids(msgs2, msgs1)
    common = [key for key in msgs1 if key in msgs2]

    if len(common) == 0:
        print('These files have nothing at all in common.', file=fd)
        raise SystemExit
    common_fraction = float(len(common)) / n1
    if common_fraction < 0.01:
        print('These files have almost nothing in common.', file=fd)
    elif common_fraction < 0.1:
        print('These files do not have much in common.', file=fd)

    if len(first_only) == 0 and len(second_only) == 0:
        assert n1 == n2
        print('Each file contains %d msgids, and they are all identical.' % n1,
              file=fd)
        print(file=fd)
    else:
        if n1 != n2:
            if n1 > n2:
                print('Total number of messages reduced by %d from %d to %d.'
                      % (n1 - n2, n1, n2), file=fd)
            else:
                assert n1 < n2
                print('Total number of messages increased by %d from %d '
                      'to %d.' % (n2 - n1, n1, n2),
                      file=fd)
            print(file=fd)
        else:
            print('Both files contain %d msgids (but they differ).' % n1,
                  file=fd)
            print(file=fd)

        if first_only:
            u, f, t = stats(msgs1[key] for key in first_only)
            print('%d msgids removed [u:%4d, f:%4d, t:%4d].'
                  % (len(first_only), u, f, t), file=fd)
        else:
            print('No msgids removed.', file=fd)

        if second_only:
            u, f, t = stats(msgs2[key] for key in second_only)
            print('%d msgids added   [u:%4d, f:%4d, t:%4d].'
                  % (len(second_only), u, f, t), file=fd)
        else:
            print('No msgids added.', file=fd)
        print('%d msgids in common.' % len(common), file=fd)
        print(file=fd)

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
                print('%d messages remain %s.' % (N, d1), file=fd)
            else:
                print('%d %s messages changed to %s.' % (N, d1, d2), file=fd)

    conflicts = 0
    for key in common:
        msg1 = msgs1[key]
        msg2 = msgs2[key]
        if msg1.istranslated and msg2.istranslated:
            for str1, str2 in zip(msg1.msgstrs, msg2.msgstrs):
                if str1 != str2:
                    conflicts += 1
    print(file=fd)
    if conflicts:
        print('There are %d conflicts among translated messages.' % conflicts,
              file=fd)
    else:
        print('There are no conflicts among translated messages.', file=fd)


@pyg3tmain(build_parser)
def main(parser):
    opts, args = parser.parse_args()

    fd = get_encoded_output('utf-8')

    if len(args) != 2:
        parser.error('Error: Requires exactly 2 files; got %d' % len(args))

    file1, file2 = args

    input1 = open(file1, 'rb')
    input2 = open(file2, 'rb')
    cat1 = parse(input1)
    cat2 = parse(input2)

    compare(cat1, cat2, fd)
