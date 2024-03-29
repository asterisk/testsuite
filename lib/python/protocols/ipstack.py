"""
TCP/IP Protocol Stack
Note: before parsing the application layer over a TCP stream, you must
first combine all the TCP frames into a stream. See utils.tcpip for
some solutions
"""
from binascii import unhexlify
#import six
#from construct import Struct, HexDump, Switch, Pass, Computed, Hex, Bytes, setGlobalPrintFullStrings
#from construct import Struct, HexDump, Switch, Pass, Computed, Hex, Bytes, setglobalfullprinting
from construct import Struct, HexDump, Switch, Pass, Computed, Hex, Bytes
from protocols.layer2.ethernet import ethernet_header
from protocols.layer3.ipv4 import ipv4_header
from protocols.layer3.ipv6 import ipv6_header
from protocols.layer4.tcp import tcp_header
from protocols.layer4.udp import udp_header

#setglobalfullprinting(True)
#setGlobalPrintFullStrings(True)

layer4_tcp = "layer4_tcp" / Struct(
    "layer" / Computed(4),
    "packet_type" / Computed("TCP"),
    "header" / tcp_header,
    "next" / Bytes(lambda ctx: ctx["_"]["header"].payload_length - ctx["header"].header_length)
)

layer4_udp = "layer4_udp" / Struct(
    "layer" / Computed(4),
    "packet_type" / Computed("UDP"),
    "header" / udp_header,
    "next" / Bytes(lambda ctx: ctx["header"].payload_length)
)

layer3_payload = "next" / Switch(lambda ctx: ctx["header"].protocol,
    {
        "TCP" : layer4_tcp,
        "UDP" : layer4_udp,
    },
    default = Pass
)

layer3_ipv4 = "layer3_ipv4" / Struct(
    "layer" / Computed(3),
    "packet_type" / Computed("IPv4"),
    "header" / ipv4_header,
    layer3_payload,
)

layer3_ipv6 = "layer3_ipv6" / Struct(
    "layer" / Computed(3),
    "packet_type" / Computed("IPv6"),
    "header" / ipv6_header,
    layer3_payload,
)

layer2_ethernet = "layer2_ethernet" / Struct(
    "layer" / Computed(2),
    "packet_type" / Computed("ETHERNET"),
    "header" / ethernet_header,
    "next" / Switch(lambda ctx: ctx["header"].type,
        {
            "IPv4" : layer3_ipv4,
            "IPv6" : layer3_ipv6,
        },
        default = Pass,
    )
)

ip_stack = "ip_stack" / layer2_ethernet


if __name__ == "__main__":
    cap1 = unhexlify(
    "0011508c283c001150886b570800450001e971474000800684e4c0a80202525eedda11"
    "2a0050d98ec61d54fe977d501844705dcc0000474554202f20485454502f312e310d0a"
    "486f73743a207777772e707974686f6e2e6f72670d0a557365722d4167656e743a204d"
    "6f7a696c6c612f352e30202857696e646f77733b20553b2057696e646f7773204e5420"
    "352e313b20656e2d55533b2072763a312e382e302e3129204765636b6f2f3230303630"
    "3131312046697265666f782f312e352e302e310d0a4163636570743a20746578742f78"
    "6d6c2c6170706c69636174696f6e2f786d6c2c6170706c69636174696f6e2f7868746d"
    "6c2b786d6c2c746578742f68746d6c3b713d302e392c746578742f706c61696e3b713d"
    "302e382c696d6167652f706e672c2a2f2a3b713d302e350d0a4163636570742d4c616e"
    "67756167653a20656e2d75732c656e3b713d302e350d0a4163636570742d456e636f64"
    "696e673a20677a69702c6465666c6174650d0a4163636570742d436861727365743a20"
    "49534f2d383835392d312c7574662d383b713d302e372c2a3b713d302e370d0a4b6565"
    "702d416c6976653a203330300d0a436f6e6e656374696f6e3a206b6565702d616c6976"
    "650d0a507261676d613a206e6f2d63616368650d0a43616368652d436f6e74726f6c3a"
    "206e6f2d63616368650d0a0d0a"
    )

    cap2 = unhexlify(
    "0002e3426009001150f2c280080045900598fd22000036063291d149baeec0a8023c00"
    "500cc33b8aa7dcc4e588065010ffffcecd0000485454502f312e3120323030204f4b0d"
    "0a446174653a204672692c2031352044656320323030362032313a32363a323520474d"
    "540d0a5033503a20706f6c6963797265663d22687474703a2f2f7033702e7961686f6f"
    "2e636f6d2f7733632f7033702e786d6c222c2043503d2243414f2044535020434f5220"
    "4355522041444d20444556205441492050534120505344204956416920495644692043"
    "4f4e692054454c6f204f545069204f55522044454c692053414d69204f54526920554e"
    "5269205055426920494e4420504859204f4e4c20554e49205055522046494e20434f4d"
    "204e415620494e542044454d20434e542053544120504f4c204845412050524520474f"
    "56220d0a43616368652d436f6e74726f6c3a20707269766174650d0a566172793a2055"
    "7365722d4167656e740d0a5365742d436f6f6b69653a20443d5f796c683d58336f444d"
    "54466b64476c6f5a7a567842463954417a49334d5459784e446b4563476c6b417a4578"
    "4e6a59794d5463314e5463456447567a64414d7742485274634777446157356b5a5867"
    "7462412d2d3b20706174683d2f3b20646f6d61696e3d2e7961686f6f2e636f6d0d0a43"
    "6f6e6e656374696f6e3a20636c6f73650d0a5472616e736665722d456e636f64696e67"
    "3a206368756e6b65640d0a436f6e74656e742d547970653a20746578742f68746d6c3b"
    "20636861727365743d7574662d380d0a436f6e74656e742d456e636f64696e673a2067"
    "7a69700d0a0d0a366263382020200d0a1f8b0800000000000003dcbd6977db38b200fa"
    "f9fa9cf90f88326dd9b1169212b5d891739cd84ed2936d1277a7d3cbf1a1484a624c91"
    "0c4979893bbfec7d7bbfec556121012eb29d65e6be7be7762c9240a1502854150a85c2"
    "c37b87af9f9c7c7873449e9dbc7c41defcf2f8c5f327a4d1ee76dff79e74bb872787ec"
    "43bfa3e9ddeed1ab06692cd234daed762f2e2e3a17bd4e18cfbb276fbb8b74e9f7bb49"
    "1a7b76da7152a7b1bff110dfed3f5cb896030f4b37b508566dbb9f56def9a4f1240c52"
    "3748db275791db20367b9a3452f732a5d0f688bdb0e2c44d27bf9c1cb7470830b1632f"
    "4a490a3578c18fd6b9c5dec2f7732b2641783109dc0b7268a56e2bd527a931497b93b4"
    "3f49cd493a98a4c3493a9aa4e349aa6bf01f7cd78d89d6b2ed49b3d9baf223f8b307b5"
    "004a67eea627ded2dddadedb78d8656de428f856305f5973779223b0fff05ebbbde1db"
    "67082a499289ae0f06863e1c8f4c0639eaccbdd9a3547abf798a1f0ec6c73fafd2e4f1"
    "51ffd5f1c9e2f9e37ff74e74fbddd941b375eadb0942b3e3d5723a69f6060373a6cff4"
    "9e6df586dac8b11c4d1f1afd81319b0df45e6fd4925a6cee6db4dbfb19e225bc1b12e5"
    "6a098aed9309715c3b74dc5fde3e7f122ea3308061dac22f4018a4f8878367af5f4f2e"
    "bcc001a2d187bfffbefeb2477f75026be9269165bb93d92ab0532f0cb68264fbda9b6d"
    "dd0b92bfff867f3abe1bccd3c5f675eca6ab3820c1caf7f7be20e05363029f93c8f7d2"
    "ad46a7b1bd475ff62614f2de2c8cb7f08537d93a35fed0fe9a4c1af44363fb91beabed"
    "790f4f0d0e7a6f67c7dbbe3eedfd01e5bcbffe9a64bf289e00307bb1f7852371dadb13"
    "3df0c3798efba9d93a1db44e87dbd7d8b4cf50e95c780e304be745389fbbf11ef4cddf"
    "dcf4b162d629fa94d7defbe2fa892b3ece2c78d8fb221a84517003476a73dc3ad535d6"
    "e22c7fbd0db8cf3a511ca6211d3e28933fed9d8ea54f381f66c0c7f2cb0e4c3898ad2b"
    "3b0de3c9e918bf25abc88d6ddf02d65581418f94174addc9ebe94717e67ce557207b6d"
    "45f892773ae393adc62af57c18ecd27b46e5aa2feea5b58c7c173e6d94be1d3bd5afa3"
    "fcf571d409ded9b1eb06ef3d275d00c36f25f4916c6ed2a911cef88b0e4c0ecfa7a5b6"
    "27936600b3d28d9bdbe411"
    )

    obj = ip_stack.parse(cap1)
    print (obj)
    # Print just the payload
    print (obj.next.next.next)
    built = ip_stack.build(obj)
    assert built == cap1

    print ("-" * 80)

    obj = ip_stack.parse(cap2)
    print (obj.next.next.header)
    built = ip_stack.build(obj)
    assert built == cap2
