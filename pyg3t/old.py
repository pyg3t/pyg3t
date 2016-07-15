class LineNumberIterator:
    # XXX Can probably be replaced by using fileinput module
    def __init__(self, input):
        self.lineno = 0
        self.input = input
        self.lines = []
        self.iter = iter(self)
        self.last_lines = []
        self.max_last_lines = 12

    def pop_lines(self):
        lines = self.lines
        self.lines = []
        return lines

    def __iter__(self):
        for line in self.input:
            self.lineno += 1
            self.last_lines.append(line)
            if len(self.last_lines) > self.max_last_lines:
                self.last_lines.pop(0)
            if line.isspace():
                continue
            yield line

    def next(self):
        return self.iter.next()


class BadSyntaxError(ValueError):
    """Error raised by subroutines when they cannot figure out what to do."""
    pass


class UnimplementedPoSyntaxError(NotImplementedError):
    """Exception for syntactical features we don't support."""
    pass


def consume_lines(nextline, input, startpattern, continuepattern):
    if startpattern.match(nextline) is None:
        raise ValueError('grrr')#BadSyntaxError
    lines = [nextline]
    for nextline in input:
        if continuepattern.match(nextline):
            lines.append(nextline)
        else:
            break
    else:
        nextline = None # EOF
    return nextline, lines


def extract_string(lines, header, continuationlength):
    line = lines[0]
    match = header.match(line)
    if not match:
        raise BadSyntaxError

    # get e.g. 'hello' from the line 'msgid "hello"', so skip 2 characters
    end = match.end()
    #assert line[end] == '"'
    headerline = line[end + 1:-2]

    # get 'hello' from line '"hello"'
    otherlines = [line[continuationlength:-2] for line in lines[1:]]
    return ''.join([headerline] + otherlines)

linepatternstrings = dict(comment=r'(#~ )?#[\s,\.:\|]|#~[,\.:\|]',
                          msgctxt=r'(#~ )?msgctxt ',
                          msgid=r'(#~ )?msgid ',
                          msgid_plural=r'(#~ )?msgid_plural ',
                          msgstr=r'(#~ )?msgstr ',
                          msgstr_plural=r'(#~ )?msgstr\[\d\] ',
                          continuation=r'(#~ )?"',
                          prevmsgid_start=r'#\| msgid ',
                          prevmsgid_continuation=r'#\| "')
linepatterns = dict([(key, re.compile(value))
                     for key, value in linepatternstrings.items()])
obsolete_linepatterns = dict([(key, re.compile(r'#~( ?)' + value))
                              for key, value in linepatternstrings.items()])


class PoParser:
    def __init__(self, input):
        self._input = input
        self.input = LineNumberIterator(input)
        self.last_chunk = None
        self.last_lines = []

    def get_message_chunks(self):
        input = self.input
        line = input.next()
        #self.last_lines.append(line)
        if len(self.last_lines) > 12:
            self.last_lines.pop()
        while True:
            msgdata = {}
            rawlines = []
            msgdata['rawlines'] = rawlines

            def _consume_lines(nextline, input, startpattern, continuepattern):
                try:
                    nextline, lines = consume_lines(nextline, input,
                                                    startpattern,
                                                    continuepattern)
                except BadSyntaxError as error:
                    msg = 'Unrecognized syntax while parsing line %d' \
                        % input.lineno
                    newerror = PoError(msg,
                                       lineno=input.lineno,
                                       original_error=error,
                                       last_lines=input.last_lines)
                    raise newerror
                rawlines.extend(lines)
                return nextline, lines

            def _extract_string(nextline, input, header):
                nextline, lines = _consume_lines(nextline, input, header,
                                                 patterns['continuation'])
                continuationlength = 1
                if lines[-1].startswith('#~ "'):
                    continuationlength = 4
                string = extract_string(lines, header, continuationlength)
                return nextline, string

            patterns = linepatterns

            if patterns['comment'].match(line):
                line, comments = _consume_lines(line, input,
                                                patterns['comment'],
                                                patterns['comment'])
            else:
                comments = []

            if line.startswith('#~'):
                # Yuck!  Comments were not obsolete, but actual msgid was.
                is_obsolete = True
                patterns = obsolete_linepatterns
            else:
                is_obsolete = False

            # At least now we are sure whether it's really obsolete
            msgdata['is_obsolete'] = is_obsolete

            flags = []
            normalcomments = []
            for i, comment in enumerate(comments):
                if patterns['prevmsgid_start'].match(comment):
                    prevmsgid_lines = iter(comments[i + 1:])
                    _, lines = consume_lines(
                        comment, prevmsgid_lines,
                        patterns['prevmsgid_start'],
                        patterns['prevmsgid_continuation'])
                    prevmsgid = extract_string(lines,
                                               patterns['prevmsgid_start'], 4)
                    msgdata['prevmsgid'] = prevmsgid
                if comment.startswith('#, '):
                    flags.extend(comment[3:].split(','))
                else:
                    normalcomments.append(comment)
            msgdata['comments'] = normalcomments
            msgdata['flags'] = [flag.strip() for flag in flags]

            if line.startswith('#~'):
                # Aha!  It was an obsolete all along!
                # Must read all remaining lines as obsolete...
                is_obsolete = True
                patterns = obsolete_linepatterns

            if patterns['msgctxt'].match(line):
                line, msgctxt = _extract_string(line, input,
                                                patterns['msgctxt'])
                msgdata['msgctxt'] = msgctxt

            if patterns['msgid'].match(line):
                line, msgid = _extract_string(line, input, patterns['msgid'])
                msgdata['msgid'] = msgid
                msgdata['lineno'] = input.lineno

            if patterns['msgid_plural'].match(line):
                line, msgid_plural = _extract_string(line, input,
                                                     patterns['msgid_plural'])
                msgdata['msgid_plural'] = msgid_plural

                nmsgstr = 0
                msgstrs = []
                pluralpattern = patterns['msgstr_plural']
                while line is not None and pluralpattern.match(line):
                    line, msgstr = _extract_string(line, input,
                                                   pluralpattern)
                    msgstrs.append(msgstr)
                    nmsgstr += 1
                msgdata['msgstrs'] = msgstrs
            else:
                line, msgstr = _extract_string(line, input, patterns['msgstr'])
                msgdata['msgstrs'] = [msgstr]
            self.last_chunk = msgdata
            yield msgdata
            if line is None:
                return

    def chunk_iter(self, include_obsoletes=False):
        return self.get_message_chunks()


def parse(input):
    parser = PoParser(input)

    try:
        fname = input.name
    except AttributeError:
        fname = '<unknown>'

    chunks = []
    obsoletes = []

    chunk = None
    for chunk in parser.chunk_iter(include_obsoletes=True):
        if chunk['is_obsolete']:
            obsoletes.append(chunk)
        else:
            chunks.append(chunk)

    for chunk in chunks:
        if chunk['msgid'] == '':
            header = chunk
            break
    else:
        raise PoHeaderError('Header not found')

    for line in header['msgstrs'][0].split('\\n'):
        if line.startswith('Content-Type:'):
            break
    for token in line.split():
        if token.startswith('charset='):
            break
    encoding = token.split('=')[1]

    msgs = []
    for chunk in chunks + obsoletes:
        msgstrs = chunk['msgstrs']

        if len(msgstrs) > 1:
            assert 'msgid_plural' in chunk

        meta = dict(rawlines=[line.decode(encoding)
                              for line in chunk['rawlines']],
                    lineno=chunk['lineno'],
                    fname=fname,
                    encoding=encoding)

        if chunk['is_obsolete']:
            msgclass = ObsoleteMessage
        else:
            msgclass = Message

        def dec(txt):
            if isinstance(txt, basestring):
                return txt.decode(encoding)
            elif txt is None:
                return None
            else:
                return txt.decode(encoding)

        msg = msgclass(msgid=dec(chunk['msgid']),
                       msgstr=[dec(m) for m in msgstrs],  # (includes plurals)
                       msgid_plural=dec(chunk.get('msgid_plural')),
                       msgctxt=dec(chunk.get('msgctxt')),
                       previous_msgid=dec(chunk.get('prevmsgid')),
                       comments=[dec(c) for c in chunk['comments']],
                       flags=[dec(f) for f in chunk['flags']],
                       meta=meta)
        msgs.append(msg)

    cat = Catalog(fname, encoding, msgs)
    return cat
