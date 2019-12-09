"""
Ethernet (TCP/IP protocol stack)
"""
from binascii import unhexlify

from construct import *
from construct.core import *
from protocols.layer3.ipv4 import IpAddress
from ethernet import MacAddress

'''
def HwAddress(name):
    return IfThenElse(name, lambda ctx: ctx.hardware_type == "ETHERNET",
        MacAddressAdapter(Field("data", lambda ctx: ctx.hwaddr_length)),
        Field("data", lambda ctx: ctx.hwaddr_length)
    )

def ProtoAddress(name):
    return IfThenElse(name, lambda ctx: ctx.protocol_type == "IP",
        IpAddressAdapter(Field("data", lambda ctx: ctx.protoaddr_length)),
        Field("data", lambda ctx: ctx.protoaddr_length)
    )
'''

def HardwareTypeEnum(code):
    return Enum(code,
        ETHERNET = 1,
        EXPERIMENTAL_ETHERNET = 2,
        ProNET_TOKEN_RING = 4,
        CHAOS = 5,
        IEEE802 = 6,
        ARCNET = 7,
        HYPERCHANNEL = 8,
        ULTRALINK = 13,
        FRAME_RELAY = 15,
        FIBRE_CHANNEL = 18,
        IEEE1394 = 24,
        HIPARP = 28,
        ISO7816_3 = 29,
        ARPSEC = 30,
        IPSEC_TUNNEL = 31,
        INFINIBAND = 32,
    )

def OpcodeEnum(code):
    return Enum(code,
        REQUEST = 1,
        REPLY = 2,
        REQUEST_REVERSE = 3,
        REPLY_REVERSE = 4,
        DRARP_REQUEST = 5,
        DRARP_REPLY = 6,
        DRARP_ERROR = 7,
        InARP_REQUEST = 8,
        InARP_REPLY = 9,
        ARP_NAK = 10
    )

arp_header = "arp_header" / Struct(
    "hardware_type" / HardwareTypeEnum(Int16ub),
    "protocol_type" / Enum(Int16ub,
        IP = 0x0800,
    ),
    "hwaddr_length" / Int8ub,
    "protoaddr_length" / Int8ub,
    "opcode" / OpcodeEnum(Int16ub),
    "source_hwaddr" / MacAddress(),
    "source_protoaddr" / IpAddress(),
    "dest_hwaddr" / MacAddress(),
    "dest_protoaddr" / IpAddress(),
)

rarp_header = "rarp_header" / arp_header

if __name__ == "__main__":
    cap1 = unhexlify(b"00010800060400010002e3426009c0a80204000000000000c0a80201")
    obj = arp_header.parse(cap1)
    print (obj)
    built = arp_header.build(obj)
    print(repr(built))
    assert built == cap1

    print ("-" * 80)
    
    cap2 = unhexlify(b"00010800060400020011508c283cc0a802010002e3426009c0a80204")
    obj = arp_header.parse(cap2)
    print (obj)
    built = arp_header.build(obj)
    print(repr(built))
    assert built == cap2













