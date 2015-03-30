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


class BobCallCallback(pj.CallCallback):
    '''Call Callback used for Alice's call to Bob

    When we get told the call state is CONFIRMED, we signal
    to the test that the call is answered
    '''

    def __init__(self, call, transfer_object):
        pj.CallCallback.__init__(self, call)
        self.transfer_object = transfer_object

    def on_state(self):
        if self.call.info().state == pj.CallState.CONFIRMED:
            reactor.callFromThread(self.transfer_object.bob_call_answered)


class CarolCallCallback(pj.CallCallback):
    '''Call Callback for Alice's call to Carol

    When we get told the call state is CONFIRMED we signal to the test that the
    call has been answered. This is very important, because if we attempt to
    perform the transfer before PJSUA has set the call state to CONFIRMED, then
    the REFER request that PJSUA sends will have a blank to-tag in the Refer-To
    header. Waiting ensures that all information is present in the REFER
    request.
    '''

    def __init__(self, call, transfer_object):
        pj.CallCallback.__init__(self, call)
        self.transfer_object = transfer_object

    def on_state(self):
        if self.call.info().state == pj.CallState.CONFIRMED:
            reactor.callFromThread(self.transfer_object.carol_call_answered)


class Transfer(object):
    '''Controller for attended transfer test

    This contains all the methods for advancing the test, such as placing calls
    and performing transfers. It also has several state variables that help to
    determine the proper timing for performing actions.
    '''

    def __init__(self, test_object, accounts):
        super(Transfer, self).__init__()
        self.ami = test_object.ami[0]
        self.ami.registerEvent('Bridge', self.bridge)
        self.ami.registerEvent('VarSet', self.bridge_peer)

        self.chans = []
        self.final_bridge = 0
        self.bob_call_up = False
        self.carol_call_up = False
        self.bridge1_bridged = False
        self.bridge2_bridged = False

        bob = accounts.get('bob').account
        bob.set_callback(TransferAccountCallback(bob))

        carol = accounts.get('carol').account
        carol.set_callback(TransferAccountCallback(carol))

        self.alice = accounts.get('alice').account
        self.call_to_bob = None
        self.call_to_carol = None

        self.test_object = test_object
        self.state = INIT

    def bridge(self, ami, event):
        if event['channel2'] in self.chans:
            return

        self.chans.append(event['channel2'])
        numchans = len(self.chans)
        if numchans == 1:
            self.bridge1_bridged = True
            self.call_carol()
        elif numchans == 2:
            self.bridge2_bridged = True
            self.transfer_call()

    def bridge_peer(self, ami, event):
        if event['variable'] != "BRIDGEPEER" or len(self.chans) < 2:
            return

        LOGGER.info("Inspecting BRIDGEPEER VarSet")

        # we should get 2 bridgepeers with swapped channel and value headers
        # indicating the bridged channels
        if self.chans[:2] == [event['channel'], event['value']] or\
            self.chans[:2] == [event['value'], event['channel']]:
            LOGGER.info("Got expected VarSet")
            self.final_bridge += 1
            if self.final_bridge == 2:
                LOGGER.info("Transfer successful!")
                # success!
                self.hangup_calls()

    def bob_call_answered(self):
        self.bob_call_up = True
        self.call_carol()

    def carol_call_answered(self):
        self.carol_call_up = True
        self.transfer_call()

    def call_bob(self):
        self.call_to_bob = self.alice.make_call('sip:bob@127.0.0.1',
                                                BobCallCallback(None, self))
        self.state = BOB_CALLED

    def call_carol(self):
        if (self.state == BOB_CALLED and self.bridge1_bridged and
                self.bob_call_up):
            self.call_to_carol = self.alice.make_call('sip:carol@127.0.0.1',
                                                      CarolCallCallback(None,
                                                                        self))
            self.state = CAROL_CALLED

    def transfer_call(self):
        if (self.state == CAROL_CALLED and self.bridge2_bridged and
                self.carol_call_up):
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
