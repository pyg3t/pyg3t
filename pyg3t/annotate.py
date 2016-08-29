from __future__ import print_function, unicode_literals
from pyg3t.util import regex


_basepattern = r'\s*#\s*pyg3t'
_annpattern = r': (?P<annotation>.*)'
_refpattern = r'-ref: (?P<fname>.+?):(?P<lineno>\d+)$'
_pattern = regex(r'%s(%s|%s)' % (_basepattern, _annpattern, _refpattern))
ref_template = '# pyg3t-ref: %(fname)s:%(lineno)s'


def annotate_ref(fname, lineno):
    return ref_template % dict(fname=fname, lineno=lineno)


def annotate(line):
    return '# pyg3t: %s' % line


def strip_annotations(msg):
    fname = None
    lineno = None
    annotations = []
    comments = []
    for comment in msg.comments:
        match = _pattern.match(comment)
        if match:
            ann = match.group('annotation')
            if ann is not None:
                annotations.append(ann)
            else:
                assert fname is None and lineno is None
                fname, lineno = match.group('fname', 'lineno')
                assert fname is not None
                lineno = int(lineno)
        else:
            comments.append(comment)
    msg.comments = comments
    # fname/lineno may be None if there are no annotations.
    return annotations, fname, lineno
