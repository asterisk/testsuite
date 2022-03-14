#!/usr/bin/env python
"""
Copyright (C) 2015, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
import time

from twisted.internet.protocol import Protocol, ClientFactory
from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)

'''The TCP client connections to create

Each item in this list is a list of strings to write on the
TCP connection once the connection is established. Even though
we are connecting to a SIP socket, we write arbitrary non-SIP
data in all cases.
'''
TCP_MESSAGES = [
    [b""],
    [b"hi, this is your tester standby"],
    [b"INVITE sip:service@127.0.0.1:5060 SIP/2.0\r\n"],
    [b"hi, this is your tester standby",
     b"hi, this is your tester, again... standby",
     b"guess who?! yup, your tester... standby\r\n"]
]


class SIPPoker(Protocol):
    def __init__(self, messages, factory):
        self.messages = messages
        self.factory = factory

    def connectionMade(self):
        '''twisted overload for when TCP connection is established

        We log the time the connection was made and then write all
        TCP messages for this particular connection
        '''
        self.factory.set_connection_time()
        for message in self.messages:
            self.transport.write(message)


class SIPClientFactory(ClientFactory):
    def __init__(self, module, messages):
        self.module = module
        self.messages = messages
        self.connection_time = None

    def buildProtocol(self, addr):
        '''twisted overload used to create client'''
        return SIPPoker(self.messages, self)

    def clientConnectionLost(self, connector, reason):
        '''twisted overload called when connection is lost

        We expect this to be called for each TCP client connection
        we have established. We also do our due diligence to ensure
        that the connection actually timed out as expected, and the
        connection was not lost for some other unexpected reason
        '''
        if not self.connection_time:
            LOGGER.error("Client lost connection before connection was made")
            self.module.failed_timeout()

        timeout = time.time() - self.connection_time
        if timeout < 4.5 or timeout > 5.5:
            LOGGER.error("Client timeout {0} outside of bounds".format(timeout))
            self.module.failed_timeout()

        LOGGER.info("Client timed out as expected")
        self.module.successful_timeout()

    def clientConnectionFailed(self, connector, reason):
        '''twisted overload indicating the TCP connection failed'''
        LOGGER.info("Client connection failed.")
        self.module.failed_timeout()

    def set_connection_time(self):
        '''Denote when the TCP connection was established'''
        self.connection_time = time.time()


class TCPTimeoutModule(object):
    '''Entry point for pluggable module

    This sets up the TCP client connections using TCP_MESSAGES
    to determine the number of clients to set up. This class
    serves as the relay between the actual connections and the
    testsuite test object.
    '''
    def __init__(self, module_config, test_object):
        self.timeouts = 0
        self.test_object = test_object
        test_object.register_ami_observer(self.ami_connected)

    def ami_connected(self, ami):
        '''Set up TCP client connections

        We do not actually require AMI, but we can ensure that Asterisk
        is fully booted and ready to accept incoming TCP connections
        once this callback is called
        '''
        for messages in TCP_MESSAGES:
            reactor.connectTCP('127.0.0.1', 5060,
                               SIPClientFactory(self, messages))

    def successful_timeout(self):
        '''A TCP client has timed out as expected

        Once all TCP client connections have timed out, the test
        passes
        '''
        self.timeouts += 1
        if self.timeouts == len(TCP_MESSAGES):
            self.test_object.set_passed(True)
            self.test_object.stop_reactor()

    def failed_timeout(self):
        '''A TCP client connection terminated incorrectly

        This may be because the connection's timeout fell outside
        of an acceptable interval, or it may be that the connection
        could not be made in the first place
        '''
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()
