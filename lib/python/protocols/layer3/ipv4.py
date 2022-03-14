"""
Internet Protocol version 4 (TCP/IP protocol stack)
"""
from binascii import unhexlify

from construct import *
from construct.core import *


class IpAddressAdapter(Adapter):
    def _encode(self, obj, context, path):
        return "".join(chr(int(b)) for b in obj.split("."))

    def _decode(self, obj, context, path):
        return ".".join(str(b) for b in obj)

def IpAddress():
    return IpAddressAdapter(Bytes(4))

def ProtocolEnum(code):
    return Enum(code,
        ICMP = 1,
        TCP = 6,
        UDP = 17,
    )

ipv4_header = "ip_header" / BitStruct(
   "version" / Nibble,
   "header_length" / ExprAdapter(Nibble,
        lambda obj, ctx: obj * 4,
        lambda obj, ctx: obj / 4
        ),
    "tos" / Struct(
        "precedence" / BitsInteger(3),
        "minimize_delay" / Flag,
        "high_throuput" / Flag,
        "high_reliability" / Flag,
        "minimize_cost" / Flag,
        Padding(1),
    ),
    "total_length" / Bytewise(Int16ub),
    "payload_length" / Computed(lambda ctx: ctx.total_length - ctx.header_length),
    "identification" / Bytewise(Int16ub),
    "flags" / Struct(
        Padding(1),
        "dont_fragment" / Flag,
        "more_fragments" / Flag,
    ),
    "frame_offset" / BitsInteger(13),
    "ttl" / Bytewise(Int8ub),
    "protocol" / Bytewise(ProtocolEnum(Int8ub)),
    "checksum" / Bytewise(Int16ub),
    "source" / Bytewise(IpAddress()),
    "destination" / Bytewise(IpAddress()),
    "options" / Computed(lambda ctx: ctx.header_length - 20),
)


if __name__ == "__main__":
    cap = unhexlify(b"4600003ca0e3000080116185c0a80205d474a126")
    obj = ipv4_header.parse(cap)
    print (obj)
    built = ipv4_header.build(obj)
    print(repr(built))
    assert built == cap








