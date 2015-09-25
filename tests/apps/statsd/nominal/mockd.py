'''
Copyright (C) 2015, Digium, Inc.
Tyler Cambron <tcambron@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)


class MockDProtocol(DatagramProtocol):
    ''' Protocol for the Mock Server to use for receiving messages.
    '''

    def __init__(self, mockd_server):
        ''' Constructor.

        Keyword Arguments:
        mockd_server -- An instance of the mock StatsD server
        '''
        self.mockd_server = mockd_server

    def datagramReceived(self, datagram, address):
        ''' AMI Newexten event handler

        Keyword Arguments:
        datagram -- The datagram that was received by the server
        address -- The address that the datagram came from

        Accept the datagram and send it to be checked against the config
        '''
        LOGGER.debug('Server received %s from %s' % (datagram, address))
        self.mockd_server.message_received(datagram)


class MockDServer(object):
    ''' Pluggable Module that acts as a mock StatsD server
    '''

    def __init__(self, config, test_object):
        ''' Constructor

        Keyword Arguments:
        config -- This object's YAML derived configuration
        test_object -- The test object it plugs onto
        '''
        self.config = config
        self.test_object = test_object
        self.packets = []
        self.test_object.register_stop_observer(self._stop_handler)
        reactor.listenUDP(8080, MockDProtocol(self))

    def message_received(self, message):
        ''' Datagram message handler

        Keyword Arguments:
        message -- The datagram that was received by the server

        Check the message against the config and pass the test if they match
        '''
        self.packets.append(message)

        if len(self.packets) == len(self.config):
            self.test_object.stop_reactor()

    def _stop_handler(self, result):
        ''' A deferred callback called as a result of the test stopping

        Keyword Arguments:
        result -- The deferred parameter passed from callback to callback
        '''
        LOGGER.info('Checking packets received')
        if len(self.packets) != len(self.config):
            LOGGER.error('Number of received packets {0} is not equal to the '
                'number of configured packets {1}'.format(len(self.packets),
                len(self.config)))
            self.test_object.set_passed(False)
            return

        failed_matches = [(actual, expected) for actual, expected in
            zip(self.packets, self.config) if actual != expected]

        if len(failed_matches) != 0:
            LOGGER.error('The following packets failed to match: {0}'
                .format(failed_matches))
            self.test_object.set_passed(False)
            return

        LOGGER.info('All packets matched')
        self.test_object.set_passed(True)
        LOGGER.debug('Test is stopping')
