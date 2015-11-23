#!/usr/bin/env python
"""Asterisk pcap pluggable modules

This module implements a suite of pluggable module for the Asterisk Test Suite
that will generate and manipulate a pcap of the message traffic during a test.

Copyright (C) 2013, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging
import binascii

sys.path.append('lib/python')

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
from construct import *
from construct.protocols.ipstack import ip_stack
try:
    from yappcap import PcapOffline
    PCAP_AVAILABLE = True
except:
    PCAP_AVAILABLE = False

import rlmi

LOGGER = logging.getLogger(__name__)


class PcapListener(object):
    """Class that creates a pcap file for a test

    Optionally, this will also provide run-time inspection of the
    received packets
    """

    def __init__(self, module_config, test_object):
        """Constructor

        Keyword arguments:
        module_config The YAML config object for this module
        test_object   The test object this module will attach to
        """

        if not PCAP_AVAILABLE:
            raise Exception('yappcap not installed')

        device = module_config.get('device')
        bpf_filter = module_config.get('bpf-filter')
        filename = module_config.get('filename')
        snaplen = module_config.get('snaplen')
        buffer_size = module_config.get('buffer-size')
        if (module_config.get('register-observer')):
            test_object.register_pcap_observer(self.__pcap_callback)
        self.debug_packets = module_config.get('debug-packets', False)

        # Let exceptions propagate - if we can't create the pcap, this should
        # throw the exception to the pluggable module creation routines
        test_object.create_pcap_listener(
            device=device,
            bpf_filter=bpf_filter,
            dumpfile=filename,
            snaplen=snaplen,
            buffer_size=buffer_size)

    def __pcap_callback(self, packet):
        """Private callback that logs packets if the configuration supports it
        """
        if (self.debug_packets):
            LOGGER.debug(str(packet))
        self.pcap_callback(packet)

    def pcap_callback(self, packet):
        """Virtual function for inspecting received packets

        Derived classes should override this to inspect packets as they arrive
        from the listener
        """
        pass


class Packet():
    """Some IP packet.

    This class acts as a base class for everything else.

    Attributes:
    packet_type     String name for the type of packet
    raw_packet      The raw bytes read off the socket
    eth_layer       The layer 2 ethernet frame
    ip_layer        The layer 3 IPv4 or IPv6 frame
    transport_layer The layer 4 TCP or UDP information
    """

    def __init__(self, packet_type, raw_packet):
        """Constructor

        Keyword Arguments:
        packet_type A text string describing what type of packet this is
        raw_packet  The bytes comprising the packet
        """

        self.packet_type = packet_type
        self.raw_packet = raw_packet
        if isinstance(self.raw_packet, str):
            self.eth_layer = None
            self.ip_layer = None
            self.transport_layer = None
        else:
            self.eth_layer = ip_stack.parse(raw_packet.data)
            self.ip_layer = self.eth_layer.next
            self.transport_layer = self.ip_layer.next


class RTCPPacket(Packet):
    """An RTCP Packet

    Attributes:
    rtcp_header     The RTCP header information
    sender_report   The SR report, if available
    receiver_report The RR report, if available
    """

    def __init__(self, raw_packet, factory_manager):
        """Constructor

        Keyword Arguments:
        raw_packet      The bytes comprising this RTCP packet
        factory_manager The packet manager that created this packet
        """
        Packet.__init__(self, packet_type='RTCP', raw_packet=raw_packet)
        self.rtcp_header = None
        self.sender_report = None
        self.receiver_report = None
        ports = factory_manager.get_global_data(self.ip_layer.header.source)
        if ports is None:
            raise Exception()
        if (ports['rtcp'] != self.ip_layer.next.header.source):
            raise Exception()
        self.__parse_raw_data(self.transport_layer.next)

    def __parse_raw_data(self, binary_blob):
        header_def = Struct('rtcp_header',
                            BitStruct('header',
                                      BitField('version', 2),
                                      Padding(1),
                                      BitField('reception_report_count', 5),
                                      ),
                            UBInt8('packet_type'),
                            UBInt16('length'),
                            UBInt32('ssrc'))
        self.rtcp_header = header_def.parse(binary_blob)
        report_block_def = GreedyRange(
            Struct(
                'report_block',
                UBInt32('ssrc'),
                BitStruct(
                    'lost_counts',
                    BitField('fraction_lost', 8),
                    BitField('packets_lost', 24)),
                UBInt32('sequence_number_received'),
                UBInt32('interarrival_jitter'),
                UBInt32('last_sr'),
                UBInt32('delay_last_sr')
            )
        )
        if self.rtcp_header.packet_type == 200:
            sender_def = Struct('sr',
                                Struct('sender_info',
                                       UBInt32('ntp_msw'),
                                       UBInt32('ntp_lsw'),
                                       UBInt32('rtp_timestamp'),
                                       UBInt32('sender_packet_count'),
                                       UBInt32('sender_octet_count')),
                                report_block_def)

            self.sender_report = sender_def.parse(binary_blob[8:])
        elif self.rtcp_header.packet_type == 201:
            receiver_def = Struct('rr',
                                  report_block_def)
            self.receiver_report = receiver_def.parse(binary_blob[8:])

    def __str__(self):
        if self.sender_report is not None:
            return "Header: %s\n%s: %s" % (self.rtcp_header, 'SR', self.sender_report)
        else:
            return 'Header: %s\n%s: %s' % (self.rtcp_header, 'RR', self.receiver_report)


class RTPPacket(Packet):
    """An RTP Packet
    """

    def __init__(self, raw_packet, factory_manager):
        """Constructor

        Keyword Arguments:
        raw_packet      The bytes comprising this RTP packet
        factory_manager The packet manager that created this packet
        """
        Packet.__init__(self, packet_type='RTP', raw_packet=raw_packet)
        ports = factory_manager.get_global_data(self.ip_layer.header.source)
        if ports is None:
            raise Exception()
        if (ports['rtp'] != self.ip_layer.next.header.source):
            raise Exception()


class SDPPacket(Packet):
    """An SDP packet.

    An SDP packet should always be owned by a SIPPacket.

    Note that this is *not* a good parser for an SDP. Rather than
    write a full SDP parser - which the tests generally don't care
    about - this class instead exposes some minimal details for
    the Test Suite tests.

    Attributes:
    ascii_packet An ASCII string representation of the SDP
    raw_packet   The raw bytes making up the SDP packet
    rtp_port     The 'audio' media RTP port
    rtcp_port    The 'audio' media RTCP port
    """

    def __init__(self, ascii_packet, raw_packet):
        """Constructor

        Keyword Arguments:
        ascii_packet The text of the SDP packet
        raw_packet   The bytes comprising this SDP packet
        """
        Packet.__init__(self, packet_type='SDP', raw_packet=raw_packet)
        self.ascii_packet = ascii_packet
        self.sdp_lines = ascii_packet.strip('\r\n').split('\r\n')
        self.rtp_port = 0
        self.rtcp_port = 0

        # Okay. So the only reason I'm looking at the SDP is to get the RTP
        # and RTCP ports out, so we can sniff those packets. A good parser here
        # would be nice, but parsing SDP sucks.
        # This assumes a single media description; assumes its audio; and
        # assumes that the RTCP port will be one greater than the RTP port.
        # That's a lot of assumptions, but I'm not going to justify the
        # engineering effort to go beyond that.
        for line in self.sdp_lines:
            if 'm=audio' not in line:
                continue
            self.rtp_port = int(line[7:line.find(' ', 8)])
            self.rtcp_port = self.rtp_port + 1


class PIDFPacket(Packet):
    """A PIDF presence body.

    Owned by SIPPacket or a MultipartPacket.

    Attributes:
    xml         The XML representation of this PIDF packet
    content_id  Unique ID of the content this packet represents
    """

    def __init__(self, ascii_packet, raw_packet, content_id):
        Packet.__init__(self, packet_type="PIDF", raw_packet=raw_packet)
        self.xml = ascii_packet.strip()
        self.content_id = content_id


class XPIDFPacket(Packet):
    """A XPIDF presence body.

    Owned by SIPPacket or a MultipartPacket.

    Attributes:
    xml         The XML representation of this XPIDF packet
    content_id  Unique ID of the content this packet represents
    """

    def __init__(self, ascii_packet, raw_packet, content_id):
        """Constructor

        Keyword Arguments:
        ascii_packet ASCII string representation of the packet
        raw_packet   Raw bytes read from the socket
        content_id   Unique ID of the content this packet represents
        """

        Packet.__init__(self, packet_type="XPIDF", raw_packet=raw_packet)
        self.xml = ascii_packet.strip()
        self.content_id = content_id


class MWIPacket(Packet):
    """An MWI body.

    Owned by SIPPacket or a MultipartPacket.

    Attributes:
    content_id       Unique ID of the content this packet represents
    voice_message    Value of the 'Voice-Message' header in the packet
    messages_waiting Value of the 'Messages-Waiting' header in the packet
    """

    def __init__(self, ascii_packet, raw_packet, content_id):
        """Constructor

        Keyword Arguments:
        ascii_packet ASCII string representation of the packet
        raw_packet   Raw bytes read from the socket
        content_id   Unique ID of the content this packet represents
        """
        headers = {}

        Packet.__init__(self, packet_type="MWI", raw_packet=raw_packet)
        self.content_id = content_id
        headers_string = ascii_packet.split('\r\n')
        for header in headers_string:
            colon_pos = header.find(':')
            headers[header[:colon_pos]] = header[colon_pos + 1:].strip()

        self.voice_message = headers.get('Voice-Message')
        self.messages_waiting = headers.get('Messages-Waiting')


class RLMIPacket(Packet):
    """An RLMI body.

    Owned either by a SIPPacket or a MultirpartPacket.

    Attributes:
    list_elem The resource list element
    """

    def __init__(self, ascii_packet, raw_packet):
        """Constructor

        Keyword Arguments:
        ascii_packet ASCII string representation of the packet
        raw_packet   Raw bytes read from the socket
        """
        Packet.__init__(self, packet_type="RLMI", raw_packet=raw_packet)
        self.list_elem = rlmi.parseString(ascii_packet.strip(), silence=True)


class MultipartPart(object):
    """A part in a MultipartPacket's body

    Attributes:
    headers    A list of headers that determine the content type and ID of the
               content packet inside the multipart part
    content_id The ID of the content packet
    body       The packet making up the content
    """

    def __init__(self, part, raw_packet):
        """Constructor

        Keyword Arguments:
        part       The raw part of this MultipartPart
        raw_packet The raw packet making up the entire MultipartPacket
        """
        self.headers = {}

        last_pos = part.find('\r\n\r\n')
        headers = part[:last_pos].split('\r\n')
        body = part[last_pos:]

        for header in headers:
            colon_pos = header.find(':')
            self.headers[header[:colon_pos]] = header[colon_pos + 1:].strip()

        content_type = self.headers.get('Content-Type')
        self.content_id = self.headers.get('Content-ID').strip('<>')

        self.body = BodyFactory.create_body(content_type, body.strip(),
                                            raw_packet, self.content_id)


class MultipartPacket(Packet):
    """A multipart body.

    Owned by a SIPPacket.

    Attributes:
    boundary The keyword that denotes the boundary in the multi-part body
    parts    A list of MultipartPart parts making up the body
    """

    def __init__(self, content_type, ascii_packet, raw_packet):
        Packet.__init__(self, packet_type="Multipart", raw_packet=raw_packet)
        self.boundary = None
        self.parts = []

        for part in content_type.split(';'):
            param, equal, value = part.partition('=')
            if param == 'boundary':
                self.boundary = '--%s' % value.strip('"')

        if not self.boundary:
            raise Exception

        parts = ascii_packet.split(self.boundary)

        # Start with the second part since the initial boundary has no content
        # before it.
        for part in parts[1:]:
            stripped = part.strip('\r\n ')
            # The final boundary in a multipart body is --boundary--
            if stripped == '--':
                break
            self.parts.append(MultipartPart(stripped, raw_packet))


class BodyFactory(object):
    """Factory that creates a Packet based on some content type specification
    """

    @staticmethod
    def create_body(content_type, ascii_packet, raw_packet, content_id=None):
        """Create a Packet based on content type

        Keyword Arguments:
        content_type  The content type of the raw packet being parsed
        ascii_packet  ASCII string representation of the raw packet
        raw_packet    Raw bytes making up the packet
        content_id    Optionally, an ID that separates content within the body

        Returns:
        A Packet of the type specified by content_type
        """

        body_type, _, _ = content_type.partition(';')
        if (body_type == 'application/sdp'):
            return SDPPacket(ascii_pack, raw_packet)
        elif (body_type == 'multipart/related'):
            return MultipartPacket(content_type, ascii_packet, raw_packet)
        elif (body_type == 'application/rlmi+xml'):
            return RLMIPacket(ascii_packet, raw_packet)
        elif (body_type == 'application/pidf+xml'):
            return PIDFPacket(ascii_packet, raw_packet, content_id)
        elif (body_type == 'application/xpidf+xml'):
            return XPIDFPacket(ascii_packet, raw_packet, content_id)
        elif (body_type == 'application/simple-message-summary'):
            return MWIPacket(ascii_packet, raw_packet, content_id)
        else:
            return Packet(body_type, raw_packet)
    pass


class SIPPacket(Packet):
    """A SIP Packet

    This is not a good SIP parser. It suffices for the Test Suite's
    purposes.

    Attributes:
    body         The body conveyed in the SIP packet
    headers      A dictionary of SIP header names and their values
    request_line The full text of the request line in the SIP packet
    ascii_packet ASCII string representation of the packet
    """

    def __init__(self, ascii_packet, raw_packet):
        """Constructor

        Keyword Arguments:
        ascii_packet The text of the SIP packet
        raw_packet   The bytes comprising this SIP packet
        """
        Packet.__init__(self, packet_type='SIP', raw_packet=raw_packet)

        self.body = None
        self.headers = {}
        self.request_line = ''
        self.ascii_packet = ascii_packet

        ascii_packet = ascii_packet.lstrip()
        last_pos = ascii_packet.find('\r\n',
                                     ascii_packet.find('Content-Length'))
        header_count = 0
        sip_packet = ascii_packet[:last_pos].split('\r\n')
        remainder_packet = ascii_packet[last_pos:]
        for header in sip_packet:
            header_count += 1
            if header_count == 1:
                self.request_line = header
                continue
            colon_pos = header.find(':')
            self.headers[header[:colon_pos]] = header[colon_pos + 1:].strip()
        if int(self.headers.get('Content-Length')) > 0:
            content_type = self.headers.get('Content-Type',
                                            'application/sdp').strip()
            self.body = BodyFactory.create_body(content_type,
                                                ascii_packet=remainder_packet,
                                                raw_packet=raw_packet)

    def __str__(self):
        return self.ascii_packet


class SIPPacketFactory():
    """A packet factory for producing SIP (and SDP) packets
    """

    def __init__(self, factory_manager):
        """Constructor

        Keyword Arguments:
        factory_manager The factory manager this class factory registers to
        """
        self._factory_manager = factory_manager

    def interpret_packet(self, packet):
        """Interpret a packet

        Keyword Arguments:
        packet The packet to interpret

        Returns:
        None if we couldn't interpret this packet
        A SIPPacket if we could
        """
        ret_packet = None
        if not isinstance(packet, str):
            hex_string = binascii.b2a_hex(packet.data[42:])
            ascii_string = hex_string.decode('hex')
        else:
            ascii_string = packet

        if ('SIP/2.0' in ascii_string):
            ret_packet = SIPPacket(ascii_string, packet)

        # If we got a SIP packet, it has an SDP, and that SDP specified an
        # RTP port and RTCP port; then set that information for this particular
        # stream in the factory manager so that the factories for RTP can
        # interpret packets correctly
        if ret_packet and ret_packet.body and \
                ret_packet.body.packet_type == 'SDP' and \
                ret_packet.body.rtp_port != 0 and \
                ret_packet.body.rtcp_port != 0:
            self._factory_manager.add_global_data(
                ret_packet.ip_layer.header.source,
                {'rtp': ret_packet.body.rtp_port,
                 'rtcp': ret_packet.body.rtcp_port})
        return ret_packet


class RTPPacketFactory():
    """A packet factory for producing RTP packets
    """

    def __init__(self, factory_manager):
        """Constructor

        Keyword Arguments:
        factory_manager The factory manager this class factory registers to
        """
        self._factory_manager = factory_manager

    def interpret_packet(self, packet):
        """Interpret a packet

        Keyword Arguments:
        packet The packet to interpret

        Returns:
        None if we couldn't interpret this packet
        A RTPPacket if we could
        """
        ret_packet = None
        try:
            ret_packet = RTPPacket(packet, self._factory_manager)
        except:
            pass
        return ret_packet


class RTCPPacketFactory():
    """A packet factory for producing RTCP packets
    """

    def __init__(self, factory_manager):
        """Constructor

        Keyword Arguments:
        factory_manager The factory manager this class factory registers to
        """
        self._factory_manager = factory_manager

    def interpret_packet(self, packet):
        """Interpret a packet

        Keyword Arguments:
        packet The packet to interpret

        Returns:
        None if we couldn't interpret this packet
        A RTCPPacket if we could
        """
        ret_packet = None
        try:
            ret_packet = RTCPPacket(packet, self._factory_manager)
        except:
            pass
        return ret_packet


class PacketFactoryManager():
    """A manager for packet factories.

    This exists primarily to expose shared data between factories.
    """

    def __init__(self):
        """Constructor
        """
        self._packet_factories = []
        self._global_data = {}

    def create_factory(self, factory_type):
        """Make me a factory!

        Keyword Arguments:
        factory_type The typename of the factory to create
        """
        factory = factory_type(self)
        self._packet_factories.append(factory)

    def add_global_data(self, key, value):
        """Add a global data value to track

        A global data value is a piece of data that a factory has discovered
        that may be of use to other factories that construct packets. This is
        basically how we can figure out what ports the RTP/RTCP packets are
        coming across.

        Keyword Arguments:
        key The key of the global data
        value The key's value (oooo)
        """
        self._global_data[key] = value

    def get_global_data(self, key):
        """Get the global data associated with some key

        Keyword Arguments:
        key The key of the global data to obtain

        Returns:
        None if we don't have it
        Something if we do
        """
        return self._global_data.get(key)

    def interpret_packet(self, packet):
        """Interpret a packet

        Iterate over all of the factories and ask them to interpret a packet.
        Keep going until one of them says they got it.

        Returns:
        An interpreted packet if some packet factory handled it
        None otherwise
        """
        interpreted_packet = None
        for factory in self._packet_factories:
            try:
                interpreted_packet = factory.interpret_packet(packet)
            except Exception as e:
                LOGGER.debug('{0} threw Exception {1}'.format(factory, e))
            if interpreted_packet is not None:
                break
        return interpreted_packet


class VOIPSniffer(object):
    """Base class for a pluggable module that wants to inspect packets

    Attributes:
    callbacks      Registered callbacks by packet type
    packet_factory The one and only PacketFactoryManager
    traces         Dictionary of sniffed message traffic, organized by
                   source address
    """

    def __init__(self, module_config, test_object):
        """Constructor

        Keyword Arguments:
        module_config The module configuration for this pluggable module
        test_object   The object we will attach to
        """
        self.packet_factory = PacketFactoryManager()
        self.packet_factory.create_factory(SIPPacketFactory)
        self.packet_factory.create_factory(RTPPacketFactory)
        self.packet_factory.create_factory(RTCPPacketFactory)
        self.callbacks = {}
        self.traces = {}

    def process_packet(self, packet, (host, port)):
        """Store a known packet in our traces and call our callbacks

        Keyword Arguments:
        packet       A raw packet received from ... something.
        (host, port) Tuple of received host and port
        """
        packet = self.packet_factory.interpret_packet(packet)
        if packet is None:
            return

        if packet.ip_layer:
            host = packet.ip_layer.header.source
        if packet.transport_layer:
            port = packet.transport_layer.header.source

        LOGGER.debug('Processing packet from {1}:{2}'.format(packet, host, port))
        if host not in self.traces:
            self.traces[host] = []
        self.traces[host].append(packet)
        if packet.packet_type not in self.callbacks:
            return
        for callback in self.callbacks[packet.packet_type]:
            callback(packet)

    def add_callback(self, packet_type, callback):
        """Add a callback function for received packets of a particular type

        Note that a particular packet type can only have a single callback

        Keyword Arguments:
        packet_type The string name of the packet type to receive
        callback    A function that takes as an argument a Packet object
        """
        if packet_type not in self.callbacks:
            self.callbacks[packet_type] = []
        self.callbacks[packet_type].append(callback)

    def remove_callbacks(self, packet_type):
        """Remove the callbacks for a particular packet type

        Keyword Arguments:
        packet_type The string name of the packet type to remove callbacks for
        """
        del self.callbacks[packet_type]


class VOIPProxy(VOIPSniffer):
    """Pluggable module that acts as a packet level proxy for VoIP packets

    This module will listen on two UDP ports, and exchange packets between
    them. Received packets on either port are looked at for SIP, RTP, and
    RTCP packets, and passed off to observers.

    Attributes:
    port  The port this proxy listens on
    rules A dictionary that maps source ports to their destination host/port
    """

    class ProxyProtocol(DatagramProtocol):
        """The twisted DatagramProtocol that swaps packets
        """

        def __init__(self, rules, cb):
            """Constructor

            Keyword Arguments:
            rules A Dictionary that maps inbound to outbound ports
            cb    Callback function to called on received packets
            """
            self.rules = rules
            self.cb = cb

        def datagramReceived(self, data, (host, port)):
            """Callback for when a datagram is received

            Keyword Arguments:
            data         The actual packet
            (host, port) Tuple of source host and port
            """
            LOGGER.debug('Proxy received from {0}:{1}\n{2}'.format(
                host, port, data))

            if port not in self.rules:
                LOGGER.debug('Dropping packet from {0}:{1}'.format(
                    host, port))
                return
            dest_host = self.rules[port].get('host', host)
            dest_port = self.rules[port]['port']
            self.cb(data, (host, port))
            LOGGER.debug('Forwarding packet to {0}:{1}'.format(
                dest_host, dest_port))
            self.transport.write(data, (dest_host, dest_port))

    DEFAULT_RULES = {5060: {'host': '127.0.0.1', 'port': 5062},
                     5062: {'host': '127.0.0.1', 'port': 5060}}

    def __init__(self, module_config, test_object):
        """Constructor

        Keyword Arguments:
        module_config The module configuration
        test_object   Our one and only test object
        """
        super(VOIPProxy, self).__init__(module_config, test_object)

        self.port = module_config.get('port', 5061)
        self.rules = module_config.get('rules', VOIPProxy.DEFAULT_RULES)

        protocol = VOIPProxy.ProxyProtocol(self.rules, self.process_packet)
        reactor.listenUDP(self.port, protocol)


class VOIPListener(VOIPSniffer, PcapListener):
    """Pluggable module class that sniffs for SIP, RTP, and RTCP packets

    Received packets are stored according to the source.

    Attributes:
    packet_factory The one and only PacketFactoryManager
    traces         Dictionary of sniffed message traffic, organized by
                   source address
    """

    def __init__(self, module_config, test_object):
        """Constructor

        Keyword Arguments:
        module_config The module configuration for this pluggable module
        test_object   The object we will attach to
        """
        if not 'register-observer' in module_config:
            raise Exception('VOIPListener needs register-observer to be set')

        super(VOIPListener, self).__init__(module_config, test_object)

    def pcap_callback(self, packet):
        """Packet capture callback function

        Overrides PcapListener's virtual function. This will interpret the
        packet using the PacketFactoryManager, and pass the parsed packet
        off to registered callbacks.

        Keyword Arguments:
        packet A received packet from the pcap listener
        """
        self.process_packet(packet, (None, None))

