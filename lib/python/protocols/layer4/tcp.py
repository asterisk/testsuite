"""
Transmission Control Protocol (TCP/IP protocol stack)
"""
from binascii import unhexlify

from construct import *
from construct.core import *

tcp_header = "tcp_header" / BitStruct(
    "source" / Bytewise(Int16ub),
    "destination" / Bytewise(Int16ub),
    "seq" / Bytewise(Int32ub),
    "ack" / Bytewise(Int32ub),
    "header_length" / ExprAdapter(Nibble,
        encoder = lambda obj, ctx: obj / 4,
        decoder = lambda obj, ctx: obj * 4,
    ),
    Padding(3),
    "flags" / Struct(
        "ns" / Flag,
        "cwr" / Flag,
        "ece" / Flag,
        "urg" / Flag,
        "ack" / Flag,
        "psh" / Flag,
        "rst" / Flag,
        "syn" / Flag,
        "fin" / Flag,
    ),
    "window" / Bytewise(Int16ub),
    "checksum" / Bytewise(Int16ub),
    "urgent" / Bytewise(Int16ub),
    "options" / Computed(lambda ctx: ctx.header_length - 20),
#    "_payload" / Bytewise(GreedyBytes),
#    "payload_length" / Computed(lambda ctx: len(ctx._payload)),

)

if __name__ == "__main__":
    cap = unhexlify(b"0db5005062303fb21836e9e650184470c9bc000031323334")
    obj = tcp_header.parse(cap)
    print (obj)
    built = tcp_header.build(obj)
    print(repr(built))
    assert cap == built
















