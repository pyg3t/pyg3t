from __future__ import print_function, unicode_literals
from codecs import lookup, StreamReaderWriter
import sys


py3 = sys.version_info[0] == 3
py2 = sys.version_info[0] == 2


class Py2Encoder:
    def __init__(self, fd, encoding):
        self.fd = fd
        self.encoding = encoding

    def write(self, txt):
        if not isinstance(txt, unicode):
            if txt == b'\n' or txt == b'':
                pass
            txt = unicode(txt)
        self.fd.write(txt.encode(self.encoding))


colors = {'blue': '0;34',
          'light red': '1;31',
          'light purple': '1;35',
          'brown': '0;33',
          'purple': '0;35',
          'yellow': '1;33',
          'dark gray': '1;30',
          'light cyan': '1;36',
          'black': '0;30',
          'light green': '1;32',
          'cyan': '0;36',
          'green': '0;32',
          'light blue': '1;34',
          'light gray': '0;37',
          'white': '1;37',
          'red': '0;31',
          'old': '1;31;41', # To do: proper names, reorganize
          'new': '1;33;42', # These are used by gtprevmsgdiff
          None: None}


def colorize(string, id):
    if id is None:
        return string
    tokens = []
    for line in string.split('\n'):
        if len(line) > 0:
            line = '\x1b[%sm%s\x1b[0m' % (id, line)
        tokens.append(line)
    return '\n'.join(tokens)


class Colorizer:
    def __init__(self, colorname):
        self.color = colors[colorname]

    def colorize(self, string):
        return colorize(string, self.color)


class NullDevice:
    def write(self, txt):
        pass


def get_bytes_output(name):
    if name == '-':
        return sys.stdout.buffer if py3 else sys.stdout
    else:
        return open(name, 'wb')


def get_bytes_input(name):
    if name == '-':
        return sys.stdin.buffer if py3 else sys.stdin
    else:
        try:
            return open(name, 'rb')
        except IOError as err:
            raise PoError('file-not-found', str(err))


def get_encoded_output(name, encoding):
    if name == '-':
        return get_encoded_stdout(encoding)
    else:
        return open(name, 'w', encoding=encoding)


def _stream_encoder(fd, encoding, errors='strict'):
    info = lookup(encoding)
    srw = StreamReaderWriter(fd, info.streamreader, info.streamwriter,
                             errors=errors)
    return srw


_unencoded_stdin = sys.stdin.buffer if sys.version_info == 3 else sys.stdin
_unencoded_stdout = sys.stdout.buffer if sys.version_info == 3 else sys.stdout
#_unencoded_stderr = sys.stderr.buffer if sys.version_info == 3 else sys.stderr


def get_encoded_stdout(encoding, errors='strict'):
    if py3:
        return _stream_encoder(sys.stdout.buffer, encoding, errors=errors)
    else:
        from util import Py2Encoder
        return Py2Encoder(sys.stdout, encoding)


def get_unencoded_stdin():
    if sys.version_info[0] == 3:
        return sys.stdin.buffer
    else:
        return sys.stdin


class PoError(Exception):
    def __init__(self, errtype, *args, **kwargs):
        # errtype is a unique short string identifying the error.
        # It is used to distinguish different errors by the test suite.
        self.errtype = errtype
        super(PoError, self).__init__(*args, **kwargs)

    def get_errmsg(self):
        return super(PoError, self).__str__()

    def __str__(self):
        msg = self.get_errmsg()
        if py2:
            msg = msg.encode(sys.stderr.encoding)
        return msg


def getfiles(args):
    for arg in args:
        if arg == '-':
            name = '<stdin>'
            yield name, sys.stdin
        else:
            fd = open(arg, 'rb')
            yield arg, fd

def pyg3tmain(build_parser):
    """Decorator for pyg3t main functions.

    Use like this:

        def build_parser():
            return OptionParser(...)

        @pyg3tmain(build_parser)
        def main(parser):
            ...

        main()

    Errors of known types will be caught by the decorator and printed
    nicely.

    gtcat is the reference example of how to use it."""
    def main_decorator(main):
        def pyg3tmain():
            try:
                parser = build_parser()
                main(parser)
            except KeyboardInterrupt:
                parser.error('Interrupted by keyboard')
            except PoError as err:
                parser.error(str(err))
        return pyg3tmain
    return main_decorator
