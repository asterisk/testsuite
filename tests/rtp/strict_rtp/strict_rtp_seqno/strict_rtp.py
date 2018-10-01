"""Strict RTP verification

This module sends a flood of RTP packets to a target after SIPP starts a
call in order to have Asterisk lock on to a new target address. It will also
send a packet after the target has been locked onto and considers the test
a success if that packet is denied.

Copyright (C) 2018, Digium, Inc.
Ben Ford <bford@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""
import logging
#from datetime import datetime

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
from twisted.internet import task

LOGGER = logging.getLogger(__name__)

class StrictRtpTester(object):
    """A pluggable module for verifying strictrtp seqno functionality"""

    class PacketSendProtocol(DatagramProtocol):
        """The twisted protocol that sends packets
        """

        def __init__(self, test_object):
            """Constructor
            """
            self.test_object = test_object

        def datagramReceived(self, data, (host, port)):
            """Callback for when a datagram is received.
            We don't want anything to happen here because we do all
            of the handling ourselves via TestEvent.

            Keyword Arguments:
            data         The actual packet
            (host, port) Tuple of source host and port
            """
            LOGGER.debug('Packet received from {0}:{1}\n{2}'.format(
                host, port, data))

    def __init__(self, module_config, test_object):
        """Constructor

        Keyword Arguments:
        module_config   The configuration for this pluggable module
        test_object     Our test object
        """
        self.send_num = 1
        self.send_task = None

        # Use the AMI callback to know when we are fully booted
        self.test_object = test_object
        test_object.register_ami_observer(self.ami_connect_cb)

    def send_packets(self, protocol, num):
        """Send packets to endpoint
        """
        idx = 1
        header = bytearray(12)
        header[0] = (2 << 6) & 0xC0
        while idx <= num:
            header[2] = (self.send_num & 0xFF00) >> 8
            header[3] = (self.send_num & 0xFF)
            protocol.transport.write(header, ('127.0.0.1', 10000))
            self.send_num = self.send_num + 1
            idx = idx + 1

    def ami_connect_cb(self, ami):
        """Callback called when AMI connects

        Keyword Arguments:
        ami The AMI manager object for our Asterisk instance
        """
        ami.registerEvent('TestEvent', self.test_event_handler)
        ami.registerEvent('Newexten', self.new_exten_handler)

    def test_event_handler(self, ami, event):
        """TestEvent handler

        Keyword Arguments:
        ami     The AMI protocol instance
        event   The TestEvent
        """
        if event['state'] == 'STRICT_RTP_LEARN':
            if event['source'] != '127.0.0.1:6000':
                LOGGER.debug("Failure: Strict RTP did not lock on to source 127.0.0.1:6000")
                self.test_object.set_passed(False)
                ami.hangup(self.channel)
                return
            self.send_task.stop()
            protocol = StrictRtpTester.PacketSendProtocol(self.test_object)
            reactor.listenUDP(6001, protocol)
            self.send_packets(protocol, 1)
        elif event['state'] == 'STRICT_RTP_CLOSED':
            if event['source'] != '127.0.0.1:6001':
                LOGGER.debug("Failure: Strict RTP dropped packet from source other than 127.0.0.1:6001")
                self.test_object.set_passed(False)
            else:
                self.test_object.set_passed(True)
            ami.hangup(self.channel)

    def new_exten_handler(self, ami, event):
        """NewExten handler

        Keyword Arguments:
        ami     The AMI protocol instance
        event   The Newexten event
        """
        def errback(err):
            LOGGER.error(err)

        if event['application'] != 'Echo':
            return
        self.channel = event['channel']
        protocol = StrictRtpTester.PacketSendProtocol(self.test_object)
        reactor.listenUDP(6000, protocol)
        self.send_task = task.LoopingCall(self.send_packets, protocol, 20)
        deferred = self.send_task.start(1.0)
        deferred.addErrback(errback)
