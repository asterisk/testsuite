"""
Message Transport Part 2 (SS7 protocol stack)
(untested)
"""
from construct import *
from binascii import unhexlify


mtp2_header = "mtp2_header" / BitStruct(
    "flag1" / Octet,
    "bsn" / BitsInteger(7),
    "bib" / Bit,
    "fsn" / BitsInteger(7),
    "sib" / Bit,
    "length" / Octet,
    "service_info" / Octet,
    "signalling_info" / Octet,
    "crc" / BitsInteger(16),
    "flag2" / Octet,
)

if __name__ == "__main__":
    cap = unhexlify(b"0bcc003500280689aa")
    obj = mtp2_header.parse(cap)
    print (obj)
    built = mtp2_header.build(obj)
    print(repr(built))
    assert cap == built


