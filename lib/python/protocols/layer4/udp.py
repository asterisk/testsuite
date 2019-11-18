"""
User Datagram Protocol (TCP/IP protocol stack)
"""
from binascii import unhexlify

from construct import *
from construct.core import *


udp_header = "udp_header" / Struct(
    "header_length" / Computed(lambda ctx: 8),
    "source" / Int16ub,
    "destination" / Int16ub,
    "payload_length" / ExprAdapter(Int16ub,
        encoder = lambda obj, ctx: obj + 8,
        decoder = lambda obj, ctx: obj - 8,
    ),
    "checksum" / Int16ub,
)

if __name__ == "__main__":
    cap = unhexlify(b"0bcc003500280689")
    obj = udp_header.parse(cap)
    print (obj)
    built = udp_header.build(obj)
    print(repr(built))
    assert cap == built


