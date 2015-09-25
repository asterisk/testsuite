'''
Copyright (C) 2015, Digium, Inc.
Tyler Cambron <tcambron@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor

sys.path.append("tests/apps/statsd/nominal")

LOGGER = logging.getLogger(__name__)


class MockDProtocol(DatagramProtocol):
    ''' Protocol for the Mock Server to receive messages through
    '''

    def __init__(self, mockd_server):
        ''' Constructor

        :param mockd_server An instance of the mock StatsD server
        '''
        self.mockd_server = mockd_server

    def datagramReceived(self, datagram, address):
        ''' AMI Newexten event handler

        :param datagram The datagram that was received by the server
        :param address The address that the datagram came from

        Accept the datagram and send it to be checked against the config
        '''
        self.mockd_server.message_received(datagram)


class MockDServer(object):
    ''' Pluggable Module object that acts as a StatsD server to examine
    UDP messages to ensure that messages are being sent correctly
    '''

    def __init__(self, config, test_object):
        ''' Constructor

        :param config This object's YAML derived configuration
        :param test_object The test object it plugs onto
        '''
        self.config = config
        self.test_object = test_object
        self.test_object.register_ami_observer(self.__on_ami_connect)
        self.test_object.register_stop_observer(self._stop_handler)
        reactor.listenUDP(8080, MockDProtocol(self))

    def message_received(self, message):
        ''' Datagram message handler

        :param message The datagram that was received by the server

        Check the message against the config and pass the test if they match
        '''
        self.message = message
        if self.config[0] == self.message:
            self.test_object.set_passed(True)
            LOGGER.debug('Test passed')
        else:
            LOGGER.debug('Message of %s does not match config' % message)

    def __on_ami_connect(self, ami):
        ''' AMI connected handler

        :param The AMI instance that just connected
        '''
        LOGGER.debug('AMI instance %s Connected' % ami)

    def _stop_handler(self, result):
        ''' A deferred callback called as a result of the test stopping

        :param result The deferred parameter passed from callback to callback
        '''
        LOGGER.debug('Test is stopping')
