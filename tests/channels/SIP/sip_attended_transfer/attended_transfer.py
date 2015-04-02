"""
Copyright (C) 2015, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
import pjsua as pj

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


class BridgeState(object):
    '''Object for tracking state of a bridge

    The main data the test cares about is the bridge's unique id and whether two
    channels have been bridged together by the bridge.
    '''
    def __init__(self):
        self.unique_id = None
        self.bridged = False


class Transfer(object):
    '''Controller for attended transfer test

    This contains all the methods for advancing the test, such as placing calls
    and performing transfers. It also has several state variables that help to
    determine the proper timing for performing actions.
    '''

    def __init__(self, test_object, accounts):
        super(Transfer, self).__init__()
        self.ami = test_object.ami[0]
        self.ami.registerEvent('BridgeCreate', self.bridge_create)
        self.ami.registerEvent('BridgeEnter', self.bridge_enter)

        # bridge1 bridges Alice and Bob
        self.bridge1 = BridgeState()
        # bridge2 bridges Alice and Carol
        self.bridge2 = BridgeState()

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

    def bridge_create(self, ami, event):
        if not self.bridge1.unique_id:
            self.bridge1.unique_id = event.get('bridgeuniqueid')
        elif not self.bridge2.unique_id:
            self.bridge2.unique_id = event.get('bridgeuniqueid')
        else:
            LOGGER.error("Unexpected third bridge created")
            self.test_object.set_passed(False)
            self.test_object.stop_reactor()

    def bridge_enter(self, ami, event):
        if (event.get('bridgeuniqueid') == self.bridge1.unique_id and
                event.get('bridgenumchannels') == '2'):
            self.bridge1.bridged = True
            if self.state == BOB_CALLED:
                self.call_carol()
            elif self.state == TRANSFERRED:
                self.hangup_calls()
            else:
                LOGGER.error("Unexpected BridgeEnter event")
                self.test_object.set_passed(False)
                self.test_object.stop_reactor()
        elif (event.get('bridgeuniqueid') == self.bridge2.unique_id and
                event.get('bridgenumchannels') == '2'):
            self.bridge2.bridged = True
            if self.state == CAROL_CALLED:
                self.transfer_call()
            elif self.state == TRANSFERRED:
                self.hangup_calls()
            else:
                LOGGER.error("Unexpected BridgeEnter event")
                self.test_object.set_passed(False)
                self.test_object.stop_reactor()

    def bob_call_confirmed(self):
        self.bob_call_answered = True
        self.call_carol()

    def carol_call_confirmed(self):
        self.carol_call_answered = True
        self.transfer_call()

    def call_bob(self):
        self.call_to_bob = self.alice.make_call('sip:bob@127.0.0.1',
                CallCallback(None, self.bob_call_confirmed))
        self.state = BOB_CALLED

    def call_carol(self):
        if self.bridge1.bridged and self.bob_call_answered:
            self.call_to_carol = self.alice.make_call('sip:carol@127.0.0.1',
                    CallCallback(None, self.carol_call_confirmed))
            self.state = CAROL_CALLED

    def transfer_call(self):
        if self.bridge2.bridged and self.carol_call_answered:
            self.call_to_bob.transfer_to_call(self.call_to_carol)
            self.state = TRANSFERRED

    def hangup_calls(self):
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
