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

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor

from construct import *

LOGGER = logging.getLogger(__name__)

def enum(**enums):
    """Make an enumeration out of the passed in values"""
    return type('Enum', (), enums)

IP_FAMILY = enum(v4=2, v6=10)

HEP_VARIABLE_TYPES = enum(auth_key=14,
                          payload=15,
                          uuid=17)

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
            self.src_addr = socket.inet_ntop(socket.AF_INET, src_addr.ipv4_addr)
            self.dst_addr = socket.inet_ntop(socket.AF_INET, dst_addr.ipv4_addr)
        elif self.ip_family == IP_FAMILY.v6:
            self.src_addr = socket.inet_ntop(socket.AF_INET6, src_addr.ipv6_addr)
            self.dst_addr = socket.inet_ntop(socket.AF_INET6, dst_addr.ipv6_addr)
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

        self.hep_chunk = Struct('hep_chunk',
            UBInt16('vendor_id'),
            UBInt16('type_id'),
            UBInt16('length'))
        hep_ctrl = Struct('hep_ctrl',
            Array(4, UBInt8('id')),
            UBInt16('length'))
        hep_ip_family = Struct('hep_ip_family',
            self.hep_chunk,
            UBInt8('ip_family'));
        hep_ip_id = Struct('hep_ip_id',
            self.hep_chunk,
            UBInt8('ip_id'))
        hep_port = Struct('hep_port',
            self.hep_chunk,
            UBInt16('port'))
        hep_timestamp_sec = Struct('hep_timestamp_sec',
            self.hep_chunk,
            UBInt32('timestamp_sec'))
        hep_timestamp_usec = Struct('hep_timestamp_usec',
            self.hep_chunk,
            UBInt32('timestamp_usec'))
        hep_protocol_type = Struct('hep_protocol_type',
            self.hep_chunk,
            UBInt8('protocol_type'))
        hep_capture_agent_id = Struct('hep_capture_agent_id',
            self.hep_chunk,
            UBInt32('capture_agent_id'))
        self.hep_generic_msg = Struct('hep_generic',
            hep_ctrl,
            hep_ip_family,
            hep_ip_id,
            Struct('src_port', hep_port),
            Struct('dst_port', hep_port),
            hep_timestamp_sec,
            hep_timestamp_usec,
            hep_protocol_type,
            hep_capture_agent_id)

    def datagramReceived(self, data, (host, port)):
        """Process a received datagram"""

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
            hep_ipv4_addr = Struct('hep_ipv4_addr',
                self.hep_chunk,
                String('ipv4_addr', 4))
            src_addr = hep_ipv4_addr.parse(data[length:])
            length += hep_ipv4_addr.sizeof()
            dst_addr = hep_ipv4_addr.parse(data[length:])
            length += hep_ipv4_addr.sizeof()
        elif parsed_hdr.hep_ip_family.ip_family == IP_FAMILY.v6:
            # IPv6
            hep_ipv6_addr = Struct('hep_ipv6_addr',
                self.hep_chunk,
                String('ipv6_addr', 16))
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
                hep_auth_key = String('hep_auth_key',
                                      hdr.length - self.hep_chunk.sizeof())
                packet.auth_key = hep_auth_key.parse(data[length:])
                length += hep_auth_key.sizeof() - self.hep_chunk.sizeof()
            elif hdr.type_id == HEP_VARIABLE_TYPES.payload:
                hep_payload = String('hep_payload',
                                     hdr.length - self.hep_chunk.sizeof())
                packet.payload = hep_payload.parse(data[length:])
                length += hep_payload.sizeof() - self.hep_chunk.sizeof()

                LOGGER.debug('Packet payload: %s' % packet.payload)
            elif hdr.type_id == HEP_VARIABLE_TYPES.uuid:
                hep_uuid = String('hep_uuid',
                                  hdr.length - self.hep_chunk.sizeof())
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
        self.packets = module_config.get('packets') or []
        bind_port = module_config.get('bind-port') or 9999

        protocol = HEPPacketHandler(self)
        reactor.listenUDP(int(bind_port), protocol)

        self.current_packet = 0

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
            LOGGER.error('Packet %d: Number of lines in SIP payload %d is ' \
                         'not expected %d', self.current_packet, len(sip_lines),
                         len(expected))
            self.test_object.set_passed(False)
            return

        for i in range(0, len(sip_lines)):
            if not re.match(expected[i], sip_lines[i]):
                LOGGER.error('Packet %d, SIP line %d: actual %s does not ' \
                             'match expected %s', self.current_packet, i,
                             sip_lines[i], expected[i])
                self.test_object.set_passed(False)

    def verify_rtcp_packet(self, payload, expected):
        """Verify an RTCP packet

        Keyword Arguments:
        payload  The actual payload
        expected The expected values
        """
        pass

    def verify_packet(self, packet):
        """Verify a packet

        Keyword Arguments:
        packet The HEPPacket to verify
        """

        self.current_packet += 1
        if self.current_packet > len(self.packets):
            LOGGER.error('Number of packets %d exceeded expected: %d' %
                         (self.current_packet, len(self.packets)))
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
        for key, value in self.packets[self.current_packet - 1].items():
            actual = getattr(packet, key, None)

            if isinstance(value, str):
                if not re.match(value, actual):
                    LOGGER.error('Packet %d: key %s expected value %s did ' \
                                 'not match %s', self.current_packet, key,
                                 value, actual)
                    self.test_object.set_passed(False)
            elif isinstance(value, int):
                if actual != value:
                    LOGGER.error('Packet %d: key %s expected value %d != ' \
                                 'actual %d', self.current_packet, key, value,
                                 actual)
                    self.test_object.set_passed(False)
            elif key == 'payload':
                if value['decode'] == 'SIP':
                    self.verify_sip_packet(actual, value['value'])
                elif value['decode'] == 'RTCP':
                    self.verify_rtcp_packet(actual, value['value'])
