"""
Copyright (C) 2015, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
import sys

sys.path.append("lib/python/asterisk")
import extension_bank

from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)

INIT = 0
RUNNING = 1

class BridgeTwelve(object):
    '''Object for tracking attributes of an Asterisk 12+ bridge

    The main data the test cares about is the bridge's unique id and whether two
    channels have been bridged together by the bridge.
    '''
    def __init__(self):
        self.unique_id = None
        self.bridged = False


class BridgeStateTwelve(object):
    '''Tracker of Bridge State for Asterisk 12+

    Since Asterisk 12+ has the concept of Bridge objects, this tracks the
    bridges by detecting when they are created. Once bridges are created, we
    determine that channels are bridged when BridgeEnter events indicate that
    two channels are present.
    '''
    def __init__(self, test_object, controller, ami):
        self.test_object = test_object
        self.controller = controller
        self.ami = ami
        self.bridge1 = BridgeTwelve()
        self.bridge2 = BridgeTwelve()
        self.bob_bridge_count = 0
        self.charlie_bridge_count = 0

        self.ami.registerEvent('BridgeCreate', self.bridge_create)
        self.ami.registerEvent('BridgeEnter', self.bridge_enter)

    def bridge_create(self, _, event):
        '''AMI event callback for BridgeCreate

        This method is responsible for gleaning the unique IDs of bridges that
        are created and saving them for later.
        '''
        if not self.bridge1.unique_id:
            self.bridge1.unique_id = event.get('bridgeuniqueid')
        elif not self.bridge2.unique_id:
            self.bridge2.unique_id = event.get('bridgeuniqueid')
        else:
            LOGGER.error("Unexpected third bridge created")
            self.test_object.set_passed(False)
            self.test_object.stop_reactor()

    def bridge_enter(self, _, event):
        '''AMI event callback for BridgeEnter

        This method makes the determination of whether the controller
        is allowed to attempt to move on to the next state based on
        the states of the two bridges involved
        '''
        if (event.get('bridgeuniqueid') == self.bridge1.unique_id and
                event.get('bridgenumchannels') == '2'):
            self.bridge1.bridged = True
            self.bob_bridge_count +=1
            if self.bob_bridge_count == 2:
                self.controller.hangup_calls()
            elif self.bob_bridge_count > 2:
                LOGGER.error("Unexpected BridgeEnter event")
                self.test_object.set_passed(False)
                self.test_object.stop_reactor()
        elif (event.get('bridgeuniqueid') == self.bridge2.unique_id and
              event.get('bridgenumchannels') == '2'):
            self.bridge2.bridged = True
            self.charlie_bridge_count +=1
            if self.charlie_bridge_count == 2:
                self.controller.hangup_calls()
            elif self.charlie_bridge_count > 2:
                LOGGER.error("Unexpected BridgeEnter event")
                self.test_object.set_passed(False)
                self.test_object.stop_reactor()

    def bridge1_bridged(self):
        '''Indicates if Alice and Bob are bridged'''

        return self.bridge1.bridged

    def bridge2_bridged(self):
        '''Indicates if Alice and Carol ar bridged'''

        return self.bridge2.bridged


class Transfer(object):
    '''Controller for attended transfer test
    '''

    def __init__(self, test_object):
        super(Transfer, self).__init__()
        self.ami = test_object.ami[0]

        self.bridge_state = BridgeStateTwelve(test_object, self, self.ami)

        self.test_object = test_object
        self.state = INIT

    def start_calls(self):
        ''' Initiate the extension bank

        On AMI connect, use the extension bank to initiate the preset call
        sequence
        '''
        extension_bank.bob_and_charlie_regwait_while_alice_calls(self.test_object)
        self.state = RUNNING

    def hangup_calls(self):
        '''Hang up remaining calls and end the test

        Once the transfer has completed, Bob and Carol will be bridged. We have
        the test hang them both up in order to clean up resources before marking
        the test as passed and stopping the reactor
        '''
        bob_hangup = {
            'Action': 'Hangup',
            'Channel': '/SIP/bob-.*/',
        }
        charlie_hangup = {
            'Action': 'Hangup',
            'Channel': '/SIP/charlie-.*/',
        }
        self.ami.sendMessage(bob_hangup)
        self.ami.sendMessage(charlie_hangup)
        self.test_object.set_passed(True)
        self.test_object.stop_reactor()
