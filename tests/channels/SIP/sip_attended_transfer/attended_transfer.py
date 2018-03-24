"""
Copyright (C) 2015, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
import pjsua as pj
import sys

from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)

INIT = 0
BOB_CALLED = 1
CAROL_CALLED = 2
TRANSFERRED = 3


class TransferAccountCallback(pj.AccountCallback):
    '''Generic Account callback for Bob and Carol.

    The sole purpose of this callback is to auto-answer
    incoming calls
    '''

    def __init__(self, account):
        pj.AccountCallback.__init__(self, account)

    def on_incoming_call(self, call):
        call.answer(200)


class CallCallback(pj.CallCallback):
    '''Call Callback used for Calls made by Alice.

    Each call has some specific action it is expected
    to take once the call has been confirmed to be
    answered. The on_state method is overridden to
    signal to the test that Alice is prepared for the
    next step
    '''

    def __init__(self, call, on_answered):
        pj.CallCallback.__init__(self, call)
        self.on_answered = on_answered

    def on_state(self):
        if self.call.info().state == pj.CallState.CONFIRMED:
            reactor.callFromThread(self.on_answered)


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
            if self.controller.state == BOB_CALLED:
                self.controller.call_carol()
            elif self.controller.state == TRANSFERRED:
                self.controller.hangup_calls()
            else:
                LOGGER.error("Unexpected BridgeEnter event")
                self.test_object.set_passed(False)
                self.test_object.stop_reactor()
        elif (event.get('bridgeuniqueid') == self.bridge2.unique_id and
              event.get('bridgenumchannels') == '2'):
            self.bridge2.bridged = True
            if self.controller.state == CAROL_CALLED:
                self.controller.transfer_call()
            elif self.controller.state == TRANSFERRED:
                self.controller.hangup_calls()
            else:
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

    This contains all the methods for advancing the test, such as placing calls
    and performing transfers. It also has several state variables that help to
    determine the proper timing for performing actions.
    '''

    def __init__(self, test_object, accounts):
        super(Transfer, self).__init__()
        self.ami = test_object.ami[0]

        self.bridge_state = BridgeStateTwelve(test_object, self, self.ami)

        self.bob_call_answered = False
        self.carol_call_answered = False

        bob = accounts.get('bob').account
        bob.set_callback(TransferAccountCallback(bob))

        carol = accounts.get('carol').account
        carol.set_callback(TransferAccountCallback(carol))

        self.alice = accounts.get('alice').account
        self.call_to_bob = None
        self.call_to_carol = None

        self.test_object = test_object
        self.state = INIT

    def bob_call_confirmed(self):
        '''PJSUA indication that the answer from Alice's call to Bob has been
        received
        '''

        self.bob_call_answered = True
        self.call_carol()

    def carol_call_confirmed(self):
        '''PJSUA indication that the answer from Alice's call to Carol has been
        received
        '''

        self.carol_call_answered = True
        self.transfer_call()

    def call_bob(self):
        '''Have Alice place a call to Bob'''

        self.call_to_bob = self.alice.make_call('sip:bob@127.0.0.1',
                CallCallback(None, self.bob_call_confirmed))
        self.state = BOB_CALLED

    def call_carol(self):
        '''Have Alice place a call to Carol

        Alice's PJSUA instance needs to have confirmed that the answer from
        Bob has arrived and Asterisk has to have Alice and Bob bridged before
        the call to Carol may be attempted. Therefore, events that indicate
        that these two prerequisites have been met will each attempt to have
        Alice call Carol.
        '''
        if self.bridge_state.bridge1_bridged() and self.bob_call_answered:
            self.call_to_carol = self.alice.make_call('sip:carol@127.0.0.1',
                    CallCallback(None, self.carol_call_confirmed))
            self.state = CAROL_CALLED

    def transfer_call(self):
        '''Have Alice transfer Bob to Carol

        Alice's PJSUA instance needs to have confirmed that the answer from
        Carol has arrived and Asterisk has to have Alice and Carol bridged
        before the call to Carol may be attempted. Therefore, events that
        indicate that these two prerequisites have been met will each attempt
        to have Alice transfer the call.
        '''

        if self.bridge_state.bridge2_bridged() and self.carol_call_answered:
            self.call_to_bob.transfer_to_call(self.call_to_carol)
            self.state = TRANSFERRED

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
        carol_hangup = {
            'Action': 'Hangup',
            'Channel': '/SIP/carol-.*/',
        }
        self.ami.sendMessage(bob_hangup)
        self.ami.sendMessage(carol_hangup)
        self.test_object.set_passed(True)
        self.test_object.stop_reactor()


def phones_registered(test_object, accounts):
    '''Entry point for attended transfer test

    When the PJSUA module has detected that all phones have registered, this
    method is called into. This initializes the test controller and sets the
    test in motion by placing the first call of the test
    '''

    transfer = Transfer(test_object, accounts)
    transfer.call_bob()
