"""
Ethernet (TCP/IP protocol stack)
"""
from binascii import hexlify, unhexlify

from construct import *
from construct.core import *


class MacAddressAdapter(Adapter):
    def _encode(self, obj, context, path):
        return unhexlify(obj.replace(b"-", b""))
    def _decode(self, obj, context, path):
        return b"-".join(hexlify(struct.pack('<i', b))[:2] for b in obj)

def MacAddress():
    return MacAddressAdapter(Bytes(6))

ethernet_header = "ethernet_header" / Struct(
    "destination" / MacAddress(),
    "source" / MacAddress(),
    "type" / Enum(Int16ub,
        IPv4=0x0800,
        ARP=0x0806,
        RARP=0x8035,
        X25=0x0805,
        IPX=0x8137,
        IPv6=0x86DD
    ),
)


if __name__ == "__main__":
    cap = unhexlify(b"0011508c283c0002e34260090800")
    obj = ethernet_header.parse(cap)
    print (obj)
    built = ethernet_header.build(obj)
    print(repr(built))
    assert built == cap

