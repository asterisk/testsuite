"""Keep alive verification

This module provides a pluggable module for the Asterisk Test Suite that
verifies keep-alive packets (CRLF) received over a TCP connection with the
PJSIP stack in Asterisk.

Copyright (C) 2014, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
from datetime import datetime

from twisted.internet import reactor, protocol

LOGGER = logging.getLogger(__name__)

received_packets = []


class KeepAliveProtocol(protocol.Protocol):
    """Twisted protocol for Asterisk PJSIP keep alives"""

    def __init__(self, test_object):
        """Constructor

        Keyword Arguments:
        test_object The one and only test object
        """
        self.test_object = test_object

    def dataReceived(self, data):
        LOGGER.debug('Received packet: {}'.format(data))
        received_packets.append((datetime.utcnow(), data))
        if len(received_packets) == 5:
            self.transport.loseConnection()


class KeepAliveFactory(protocol.ClientFactory):
    """Twisted protocol factory for KeepAliveProtocol"""

    def __init__(self, test_object):
        """Constructor

        Keyword Arguments:
        test_object The one and only test object
        """
        self.test_object = test_object

    def buildProtocol(self, addr):
        """Build a KeepAliveProtocol"""
        return KeepAliveProtocol(self.test_object)

    def clientConnectionFailed(self, connector, reason):
        """twisted callback for a failed client connection"""
        LOGGER.warn('Failed to connect to Asterisk on port 5060: {}'.format(
            reason))
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()

    def clientConnectionLost(self, connector, reason):
        """twisted callback for a lost client connection"""
        LOGGER.info('Client connection dropped: {}'.format(reason))
        self.test_object.stop_reactor()


class KeepAliveReceiver(object):
    """A pluggable module for verifying the keep_alive_interval option"""

    def __init__(self, module_config, test_object):
        """Constructor

        Keyword Arguments:
        module_config The configuration for this pluggable module
        test_object   The one and only test object
        """

        # Use the AMI callback to know for sure we are fully booted
        self.test_object = test_object
        test_object.register_ami_observer(self.ami_connect_cb)
        test_object.register_stop_observer(self.stop_cb)

    def ami_connect_cb(self, ami):
        """Callback called when AMI connects

        Keyword Arguments:
        ami The AMI manager object for our Asterisk instance
        """
        reactor.connectTCP('localhost', 5060,
                           KeepAliveFactory(self.test_object))

    def stop_cb(self, result):
        """Deferred callback called when Asterisk is stopped

        Used to verify that we got our packets.
        """
        if len(received_packets) != 5:
            LOGGER.warn('Failed to get 5 packets: got {} instead'.format(
                len(received_packets)))
            self.test_object.set_passed(False)
            return result

        deltas = [round((j[0] - i[0]).total_seconds()) for i, j in
                  zip(received_packets[:-1], received_packets[1:])]
        if not all([d == 2 for d in deltas]):
            LOGGER.warn('Failed to get expected deltas between keep-alives')
            LOGGER.warn('Deltas: {}'.format(deltas))
            LOGGER.warn('Received packets: {}'.format(received_packets))
            self.test_object.set_passed(False)
            return result

        if not all([p[1] == '\r\n\r\n' for p in received_packets]):
            LOGGER.warn('Failed to get expected keep-alive values')
            LOGGER.warn('Received packets: {}'.format(received_packets))
            self.test_object.set_passed(False)
            return result

        self.test_object.set_passed(True)
        return result
