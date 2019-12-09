"""
Internet Protocol version 6 (TCP/IP protocol stack)
"""
from binascii import unhexlify
from construct import *
from construct.core import *
from protocols.layer3.ipv4 import ProtocolEnum


class Ipv6AddressAdapter(Adapter):
    def _encode(self, obj, context, path):
        return "".join(part.decode("hex") for part in obj.split(":"))
    def _decode(self, obj, context, path):
        return ":".join(b.encode("hex") for b in obj)

def Ipv6Address():
    return Ipv6AddressAdapter(Bytes(16))


ipv6_header = "ip_header" / BitStruct(
    "version" / OneOf(BitsInteger(4), [6]),
    "traffic_class" / BitsInteger(8),
    "flow_label" / BitsInteger(20),
    "payload_length" / Bytewise(Int16ub),
    "protocol" / Bytewise(ProtocolEnum(Int8ub)),
    "ttl" / Bytewise(Int8ub),
    "source" / Bytewise(Ipv6Address()),
    "destination" / Bytewise(Ipv6Address()),
)


if __name__ == "__main__":
    cap = unhexlify(b"6ff0000001020680" b"0123456789ABCDEF" b"FEDCBA9876543210" b"FEDCBA9876543210" b"0123456789ABCDEF")
    obj = ipv6_header.parse(cap)
    print (obj)
    built = ipv6_header.build(obj)
    print(repr(built))
    assert built == cap

