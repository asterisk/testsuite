#!/usr/bin/env python
"""HEP Capture Server emulation/pluggable modules

This module provides a pluggable module for the Asterisk Test Suite that
emulates a HEP capture server. It receives packets from Asterisk instances
and verifies that the sent packets match their expected values.

Copyright (C) 2014, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import socket
import logging
import re
import json

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor

from construct import *
from construct.core import *

LOGGER = logging.getLogger(__name__)

from asterisk.test_suite_utils import all_match

def enum(**enums):
    """Make an enumeration out of the passed in values"""
    return type('Enum', (), enums)

IP_FAMILY = enum(v4=2, v6=10)

HEP_VARIABLE_TYPES = enum(auth_key=14,
                          payload=15,
                          uuid=17)

HEP_PROTOCOL_TYPE = enum(SIP=1,
                         H323=2,
                         SDP=3,
                         RTP=4,
                         RTCP=5,
                         MGCP=6,
                         MEGACO=7,
                         M2UA=8,
                         M3UA=9,
                         IAX=10)

HEP_PROTOCOL_TYPES_TO_STRING = {
    HEP_PROTOCOL_TYPE.SIP: 'SIP',
    HEP_PROTOCOL_TYPE.H323: 'H323',
    HEP_PROTOCOL_TYPE.SDP: 'SDP',
    HEP_PROTOCOL_TYPE.RTP: 'RTP',
    HEP_PROTOCOL_TYPE.RTCP: 'RTCP',
    HEP_PROTOCOL_TYPE.MGCP: 'MGCP',
    HEP_PROTOCOL_TYPE.MEGACO: 'MEGACO',
    HEP_PROTOCOL_TYPE.M2UA: 'M2UA',
    HEP_PROTOCOL_TYPE.M3UA: 'M3UA',
    HEP_PROTOCOL_TYPE.IAX: 'IAX',
}

class HEPPacket(object):
    """A HEP packet"""

    def __init__(self, hep_hdr, src_addr, dst_addr):
        """Constructor

        Keyword Arguments:
        hep_hdr The header read from the protocol
        src_addr The source addresses
        dst_addr The destination address
        """
        self.hep_ctrl = hep_hdr.hep_ctrl.id
        self.ip_family = hep_hdr.hep_ip_family.ip_family
        self.ip_id = hep_hdr.hep_ip_id.ip_id
        self.src_port = hep_hdr.src_port.hep_port.port
        self.dst_port = hep_hdr.dst_port.hep_port.port
        self.time_sec = hep_hdr.hep_timestamp_sec.timestamp_sec
        self.time_usec = hep_hdr.hep_timestamp_usec.timestamp_usec
        self.protocol_type = hep_hdr.hep_protocol_type.protocol_type
        self.capture_agent_id = hep_hdr.hep_capture_agent_id.capture_agent_id
        if self.ip_family == IP_FAMILY.v4:
            self.src_addr = socket.inet_ntop(socket.AF_INET, bytes(src_addr.ipv4_addr,"utf-8"))
            self.dst_addr = socket.inet_ntop(socket.AF_INET, bytes(dst_addr.ipv4_addr,"utf-8"))
        elif self.ip_family == IP_FAMILY.v6:
            self.src_addr = socket.inet_ntop(socket.AF_INET6, bytes(src_addr.ipv6_addr,"utf-8"))
            self.dst_addr = socket.inet_ntop(socket.AF_INET6, bytes(dst_addr.ipv6_addr,"utf-8"))
        self.auth_key = None
        self.uuid = None
        self.payload = None

class HEPPacketHandler(DatagramProtocol):
    """A twisted DatagramProtocol that converts a UDP packet
    into a HEPv3 packet object
    """

    def __init__(self, module):
        """Constructor

        Keyword Arguments:
        module The pluggable module that created this object
        """

        self.module = module

        self.hep_chunk = 'hep_chunk' / Struct(
            'vendor_id' / Int16ub,
            'type_id' / Int16ub,
            'length' / Int16ub)
        hep_ctrl = 'hep_ctrl' / Struct(
            'id' / Array(4, Int8ub),
            'length' / Int16ub)
        hep_ip_family = 'hep_ip_family' / Struct(
            self.hep_chunk,
            'ip_family' / Int8ub);
        hep_ip_id = 'hep_ip_id' / Struct(
            self.hep_chunk,
            'ip_id' / Int8ub)
        hep_port = 'hep_port' / Struct(
            self.hep_chunk,
            'port' / Int16ub)
        hep_timestamp_sec = 'hep_timestamp_sec' / Struct(
            self.hep_chunk,
            'timestamp_sec' / Int32ub)
        hep_timestamp_usec = 'hep_timestamp_usec' / Struct(
            self.hep_chunk,
            'timestamp_usec' / Int32ub)
        hep_protocol_type = 'hep_protocol_type' / Struct(
            self.hep_chunk,
            'protocol_type' / Int8ub)
        hep_capture_agent_id = 'hep_capture_agent_id' / Struct(
            self.hep_chunk,
            'capture_agent_id' / Int32ub)
        self.hep_generic_msg = 'hep_generic' / Struct(
            hep_ctrl,
            hep_ip_family,
            hep_ip_id,
            'src_port' / Struct(hep_port),
            'dst_port' / Struct(hep_port),
            hep_timestamp_sec,
            hep_timestamp_usec,
            hep_protocol_type,
            hep_capture_agent_id)

    def datagramReceived(self, data, addr):
        """Process a received datagram"""

        (host, port) = addr

        LOGGER.debug("Received %r from %s:%d (len: %d)" %
            (data, host, port, len(data)))

        # Parse out the header
        parsed_hdr = self.hep_generic_msg.parse(data)
        length = self.hep_generic_msg.sizeof()

        # Get the IPv4 or IPv6 addresses
        src_addr = None
        dst_addr = None
        if parsed_hdr.hep_ip_family.ip_family == IP_FAMILY.v4:
            # IPv4
            hep_ipv4_addr = 'hep_ipv4_addr' / Struct(
                self.hep_chunk,
                'ipv4_addr' / PaddedString(4, "ascii"))
            src_addr = hep_ipv4_addr.parse(data[length:])
            length += hep_ipv4_addr.sizeof()
            dst_addr = hep_ipv4_addr.parse(data[length:])
            length += hep_ipv4_addr.sizeof()
        elif parsed_hdr.hep_ip_family.ip_family == IP_FAMILY.v6:
            # IPv6
            hep_ipv6_addr = 'hep_ipv6_addr' / Struct(
                self.hep_chunk,
                'ipv6_addr' / PaddedString(16, "ascii"))
            src_addr = hep_ipv6_addr.parse(data[length:])
            length += hep_ipv6_addr.sizeof()
            dst_addr = hep_ipv6_addr.parse(data[length:])
            length += hep_ipv6_addr.sizeof()

        packet = HEPPacket(parsed_hdr, src_addr, dst_addr)

        # Get variable length fields
        while length < len(data):
            hdr = self.hep_chunk.parse(data[length:])
            length += self.hep_chunk.sizeof()
            if hdr.type_id == HEP_VARIABLE_TYPES.auth_key:
                hep_auth_key = 'hep_auth_key' / PaddedString(
                                      hdr.length - self.hep_chunk.sizeof(), "ascii")
                packet.auth_key = hep_auth_key.parse(data[length:])
                length += hep_auth_key.sizeof() - self.hep_chunk.sizeof()
            elif hdr.type_id == HEP_VARIABLE_TYPES.payload:
                hep_payload = 'hep_payload' / PaddedString(
                                     hdr.length - self.hep_chunk.sizeof(), "ascii")
                packet.payload = hep_payload.parse(data[length:])
                length += hep_payload.sizeof() - self.hep_chunk.sizeof()

                LOGGER.debug('Packet payload: %s' % packet.payload)
            elif hdr.type_id == HEP_VARIABLE_TYPES.uuid:
                hep_uuid = 'hep_uuid' / PaddedString(
                                  hdr.length - self.hep_chunk.sizeof(), "ascii")
                packet.uuid = hep_uuid.parse(data[length:])
                length += hep_uuid.sizeof() - self.hep_chunk.sizeof()
        self.module.verify_packet(packet)


class HEPCaptureNode(object):
    """Pluggable module that listens for HEP packets and verifies them"""

    def __init__(self, module_config, test_object):
        """Constructor

        Keyword Arguments:
        module_config The configuration for this pluggable module
        test_object   The one and only test object
        """
        self.test_object = test_object
        self.packets = module_config.get('packets', [])
        self.black_list = module_config.get('packet-blacklist', [])
        self.match_any = module_config.get('match-any', False)
        bind_port = module_config.get('bind-port', 9999)

        protocol = HEPPacketHandler(self)
        LOGGER.info('HEP Capture Agent: binding to %d' % (int(bind_port)))
        reactor.listenUDP(int(bind_port), protocol)

        self.current_packet = 0

        self.test_object.register_stop_observer(self.on_stop_handler)

    def on_stop_handler(self, result):
        """A deferred callback called when the test is stopped

        result The result of the previous deferreds
        """
        if len(self.packets):
            LOGGER.error('Still waiting on %d packets!' % len(self.packets))
            self.test_object.set_passed(False)
        self.test_object.set_passed(True)

    def verify_sip_packet(self, payload, expected):
        """Verify a SIP packet

        This should in no way be taken as a legitimate SIP parser. That is not
        its intended purpose. It's enough for our purposes, which is *very*
        limited.

        Keyword Arguments:
        payload  The actual payload
        expected The expected values
        """
        sip_lines = [line for line in payload.split('\r\n') if line]

        if len(sip_lines) != len(expected):
            LOGGER.debug('Packet %d: Number of lines in SIP payload %d is ' \
                         'not expected %d', self.current_packet, len(sip_lines),
                         len(expected))
            return False

        for i in range(0, len(sip_lines)):
            if not re.match(expected[i], sip_lines[i]):
                LOGGER.debug('Packet %d, SIP line %d: actual %s does not ' \
                             'match expected %s', self.current_packet, i,
                             sip_lines[i], expected[i])
                return False
        return True

    def verify_rtcp_packet(self, payload, expected):
        """Verify an RTCP packet

        Keyword Arguments:
        payload  The actual payload
        expected The expected values
        """
        return all_match(expected, json.loads(payload))

    def match_expected_packet(self, actual_packet, expected_packet):
        """Verify a received packet against an expected packet

        Keyword Arguments:
        actual_packet The received packet
        expected_packet The packet we think we should have gotten

        Returns:
        True if they matched
        False otherwise
        """
        res = True

        for key, value in expected_packet.items():
            actual = getattr(actual_packet, key, None)

            if isinstance(value, str):
                if not re.match(value, actual):
                    LOGGER.debug('Packet %d: key %s expected value %s did ' \
                                 'not match %s', self.current_packet, key,
                                 value, actual)
                    res = False
            elif isinstance(value, int):
                if actual != value:
                    LOGGER.debug('Packet %d: key %s expected value %d != ' \
                                 'actual %d', self.current_packet, key, value,
                                 actual)
                    res = False
            elif key == 'payload':
                if value['decode'] == 'SIP':
                    res = self.verify_sip_packet(actual, value['value'])
                elif value['decode'] == 'RTCP':
                    res = self.verify_rtcp_packet(actual, value['value'])
        return res

    def verify_packet(self, packet):
        """Verify a packet

        Keyword Arguments:
        packet The HEPPacket to verify
        """

        # pro-actively get the type out of the packet so we can ignore it
        # safely if we don't care about it
        packet_type = HEP_PROTOCOL_TYPES_TO_STRING.get(packet.protocol_type)
        if packet_type in self.black_list:
            LOGGER.debug('Ignoring packet of type "%s"' % packet_type)
            return

        self.current_packet += 1
        if not len(self.packets):
            LOGGER.error('Number of packets %d exceeded expected' %
                (self.current_packet))
            self.test_object.set_passed(False)
            return

        # Verify things we can do without input
        time_sec = getattr(packet, 'time_sec', None)
        if not time_sec:
            LOGGER.error('No time_sec value in packet %d: %s' %
                         (self.current_packet, str(packet.__dict__)))
            self.test_object.set_passed(False)
        time_usec = getattr(packet, 'time_usec', None)
        if not time_usec:
            LOGGER.error('No time_usec value in packet %d: %s' % (
                self.current_packet, str(packet.__dict__)))
            self.test_object.set_passed(False)

        # HEP header is always the same. The values in the array
        # of length 4 are 'HEP3'. The hep_ctrl portion of the packet
        # should always have the bytes corresponding to those
        # characters.
        hep_ctrl = getattr(packet, 'hep_ctrl', None)
        if hep_ctrl:
            if not (hep_ctrl[0] == 72 and hep_ctrl[1] == 69 and
                    hep_ctrl[2] == 80 and hep_ctrl[3] == 51):
                LOGGER.error('hep_ctrl header is not expected in ' \
                             'packet %d: %s' % (self.current_packet,
                             str(hep_ctrl)))
                self.test_object.set_passed(False)
        else:
            LOGGER.error('No hep_ctrl value in packet %d: %s' % (
                         self.current_packet, str(packet.__dict__)))
            self.test_object.set_passed(False)

        # Verify the keys specified in the YAML
        if self.match_any:
            i = 0
            for expected_packet in self.packets:
                if self.match_expected_packet(packet, expected_packet):
                    LOGGER.debug('Found a match for packet %d' %
                        self.current_packet)
                    self.packets.remove(expected_packet)
                    break
                i += 1
            else:
                LOGGER.error('Failed to find match for packet %d: %s' %
                    (self.current_packet, str(packet.__dict__)))
                self.test_object.set_passed(False)
        else:
            expected_packet = self.packets.pop(0)
            if not self.match_expected_packet(packet, expected_packet):
                LOGGER.error('Failed to match packet %d: %s' %
                    (self.current_packet, str(packet.__dict__)))
                self.test_object.set_passed(False)
