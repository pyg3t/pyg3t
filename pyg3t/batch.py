from pyg3t.gtparse import iparse
from pyg3t.util import get_encoded_output, get_bytes_input


class Batch:
    def __init__(self, op, outputfile='-'):
        self.op = op
        self.outputfile = get_encoded_output('utf-8', outputfile)

    def run(self, inputfile, outputfile=None):
        if outputfile is None:
            outputfile = self.outputfile
        else:
            outputfile = get_encoded_output('utf-8', outputfile)

        for msg in iparse(get_bytes_input(inputfile)):
            msg.meta['filename'] = inputfile
            msg = self.op(msg)
            if msg is not None:
                print(msg.tostring(), file=outputfile)
