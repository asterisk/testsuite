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

sys.path.append("lib/python")
sys.path.append("tests/apps/statsd")

LOGGER = logging.getLogger(__name__)


class MockDProtocol(DatagramProtocol):
    '''Protocol for the Mock Server to use for receiving messages.
    '''

    def __init__(self, mockd_server):
        '''Constructor.

        Keyword Arguments:
        mockd_server -- An instance of the mock StatsD server
        '''
        self.mockd_server = mockd_server

    def datagramReceived(self, datagram, address):
        '''AMI Newexten event handler

        Keyword Arguments:
        datagram -- The datagram that was received by the server
        address -- The address that the datagram came from

        Accept the datagram and send it to be checked against the config
        '''
        skip = 'stasis.message'
        LOGGER.debug('Server received %s from %s' % (datagram, address))

        if not skip in datagram:
            self.mockd_server.message_received(datagram)


class MockDServer(object):
    '''Pluggable Module that acts as a mock StatsD server
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
        self.test_object.register_ami_observer(self.ami_connect)
        self.test_object.register_stop_observer(self._stop_handler)
        reactor.listenUDP(8125, MockDProtocol(self))

    def ami_connect(self, ami):
        '''Handles the AMI connect event.'''
        ami.registerEvent('UserEvent', self._user_event_handler)

    def check_message(self, message, is_user_event):
        '''Checks a received message.

        Keyword Arguments:
        message -- The message to check.
        is_user_event -- Whether or not the message was from a user event.
        '''
        is_correct = False
        message_type = ""

        if is_user_event:
            message_type = 'UserEvent'
            message = message['UserEvent']
        else:
            message_type = 'StatsDCommand'

        for section in self.config:
            if message in section[message_type]:
                is_correct = True
                LOGGER.debug('%s found in config' % message)
                break
        else:
            LOGGER.error('%s not specified in configuration' % message)
            self.test_object.set_passed(False)
            self.test_object.stop_reactor()

    def message_received(self, message):
        '''Datagram message handler

        Keyword Arguments:
        message -- The datagram that was received by the server

        Check the message against the config and pass the test if they match
        '''
        self.packets.append(message)

        self.check_message(message, False)

    def _user_event_handler(self, ami, event):
        '''User Event handler

    	Keyword Arguments:
    	ami -- The ami instance that detected the user event
    	event -- The user event that was detected

    	Pass along a user event to check_message for validation
    	'''
        self.check_message(event, True)

    def _stop_handler(self, result):
        '''A deferred callback called as a result of the test stopping

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
