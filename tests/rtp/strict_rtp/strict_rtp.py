"""Strict RTP verification

This module sends a flood of RTP packets to a target and considers the
test failed if we receive any traffic back.

Copyright (C) 2017, Digium, Inc.
Joshua Colp <jcolp@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
from datetime import datetime

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)


class StrictRtpTester(object):
    """A pluggable module for verifying the strict RTP functionality"""

    class NoAnswerProtocol(DatagramProtocol):
        """The twisted NoAnswerProtocol that fails the test if any packets are received
        """

        def __init__(self, test_object):
            """Constructor

            Keyword Arguments:
            test_object Our one and only test object
            """
            self.test_object = test_object

        def datagramReceived(self, data, (host, port)):
            """Callback for when a datagram is received

            Keyword Arguments:
            data         The actual packet
            (host, port) Tuple of source host and port
            """
            LOGGER.debug('Packet received from {0}:{1}\n{2}'.format(
                host, port, data))

            self.test_object.set_passed(False)

    def __init__(self, module_config, test_object):
        """Constructor

        Keyword Arguments:
        module_config The configuration for this pluggable module
        test_object   The one and only test object
        """

        self.packet_count = 8

        # Use the AMI callback to know for sure we are fully booted
        self.test_object = test_object
        test_object.register_ami_observer(self.ami_connect_cb)

    def ami_connect_cb(self, ami):
        """Callback called when AMI connects

        Keyword Arguments:
        ami The AMI manager object for our Asterisk instance
        """
        ami.registerEvent('RTCPReceived', self.rtcp_received_handler)

    def rtcp_received_handler(self, ami, event):
        """RTCPReceived callback

        Keyword Arguments:
        ami   The AMI protocol instance
        event The Newchannel event
        """
        if event['sentpackets'] != '250':
            return

        self.test_object.set_passed(True)
        protocol = StrictRtpTester.NoAnswerProtocol(self.test_object)
        reactor.listenUDP(0, protocol)

        # Determine the target of the packets from the RTCPReceived event
        (host, port) = event["to"].split(":")

        # Construct a minimal RTP header by setting the version to 2
        header = bytearray(12)
        header[0] = (2 << 6) & 0xC0

        for packet in range(self.packet_count):
            # Set the sequence number to the packet number
            header[2] = (packet & 0xFF00) >> 8
            header[3] = (packet & 0xFF)
            protocol.transport.write(header, (host, int(port) - 1))
