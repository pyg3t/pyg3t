import sys

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
          'old': '1;31;41', # To do: proper names
          'new': '1;33;42',
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

def getfiles(args):
    for arg in args:
        if arg == '-':
            name = '<stdin>'
            yield name, sys.stdin
        else:
            fd = open(arg)
            yield arg, fd
