"""
Copyright (C) 2014, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging

LOGGER = logging.getLogger(__name__)

# Initial state. Bob has registered, but no calls have been placed yet.
INITIAL = 0
# Asterisk A has placed a call to Bob.
BOB_CALLED = 1
# Asterisk A and Bob are bridged, and now Bob has placed a call to Asterisk B.
AST_B_CALLED = 2
# Bob and Asterisk B are bridged, and Bob has now initiated the remote attended
# transfer
TRANSFER_INITIATED = 3
# Asterisk A and Asterisk B are now bridged, and so the call is now being hung
# up.
HANGING_UP = 4

#class BobAccountCallback(pj.AccountCallback):
#    def __init__(self, account):
#        pj.AccountCallback.__init__(self, account)
#        self.incoming_call = None
#
#    def on_incoming_call(self, call):
#        LOGGER.info("Bob has incoming call from Asterisk A. Answering")
#        call.answer(200)
#        self.incoming_call = call


class Transfer(object):
    def __init__(self, test_object):
        super(Transfer, self).__init__()
        self.ami_a = test_object.ami[0]

        # BridgeEnter and BridgeLeave for Asterisk A are used to count the
        # number of bridged channels. When two channels are bridged, then we
        # know that a call is up and we can move on to the next state.
        self.ami_a.registerEvent('BridgeEnter', self.ami_a_bridge_enter)
        self.ami_a.registerEvent('BridgeLeave', self.ami_a_bridge_leave)
        self.a_bridged_channels = 0

        # BridgeEnter and BridgeLeave for Asterisk B are used for the same
        # purposes as for Asterisk A.
        self.ami_b = test_object.ami[1]
        self.ami_b.registerEvent('BridgeEnter', self.ami_b_bridge_enter)
        self.ami_b.registerEvent('BridgeLeave', self.ami_b_bridge_leave)
        self.b_bridged_channels = 0

        # Newchannel and Hangup events are used as a way of globally counting
        # the number of channels on both Asterisk A and Asterisk B. We know the
        # scenario can be stopped when the total number of channels reaches 0 on
        # a hangup.
        self.ami_a.registerEvent('Newchannel', self.ami_new_channel)
        self.ami_b.registerEvent('Newchannel', self.ami_new_channel)
        self.ami_a.registerEvent('Hangup', self.ami_hangup)
        self.ami_b.registerEvent('Hangup', self.ami_hangup)
        self.channels = 0

#        self.bob = bob
#        self.bob_callback = BobAccountCallback(self.bob)
#        self.bob.set_callback(self.bob_callback)
#        self.call_from_bob = None

        self.test_object = test_object
        self.state = INITIAL

    def ami_a_bridge_enter(self, ami, event):
        LOGGER.info("Asterisk A channel {0} entered "
                    "bridge".format(event['channel']))

        if self.state == BOB_CALLED:
            self.a_bridged_channels += 1
            if self.a_bridged_channels == 2:
                LOGGER.info("Initial bridge complete, placing call from Bob to B")
#                self.call_from_bob = self.bob.make_call(
#                        'sip:echo@127.0.0.1:5061', pj.CallCallback())
                self.state = AST_B_CALLED
        elif self.state == TRANSFER_INITIATED:
            self.a_bridged_channels += 1
            if self.a_bridged_channels == 2:
                LOGGER.info("Second bridge complete, Hanging up call")
                hangup_msg = {
                    'Action': 'Hangup',
                    'Channel': 'Local/echo@default-00000000;2',
                }
                self.ami_a.sendMessage(hangup_msg)
                self.state = HANGING_UP
        else:
            LOGGER.error("Received BridgeEnter event during unexpected state "
                         "{0}".format(self.state))

    def ami_a_bridge_leave(self, ami, event):
        LOGGER.info("Asterisk A channel {0} left "
                    "bridge".format(event['channel']))
        self.a_bridged_channels -= 1

    def ami_b_bridge_enter(self, ami, event):
        LOGGER.info("Asterisk B channel {0} entered "
                    "bridge".format(event['channel']))

        if self.state == AST_B_CALLED:
            self.b_bridged_channels += 1
            if self.b_bridged_channels == 2:
                LOGGER.info("Initial bridge complete. Can now perform transfer")
#                self.bob_callback.incoming_call.transfer_to_call(self.call_from_bob)
                self.state = TRANSFER_INITIATED

    def ami_b_bridge_leave(self, ami, event):
        LOGGER.info("Asterisk B channel {0} left "
                    "bridge".format(event['channel']))
        self.b_bridged_channels -= 1

    def ami_new_channel(self, ami, event):
        self.channels += 1

    def ami_hangup(self, ami, event):
        self.channels -= 1

        if self.channels == 0:
            LOGGER.info("All channels hung up! Ending Test")
            self.test_object.set_passed(True)
            self.test_object.stop_reactor()

    def call_bob(self):
        originate_msg = {
            'Action': 'Originate',
            'Channel': 'Local/echo@default',
            'Exten': 'bob',
            'Context': 'default',
            'Priority': '1',
        }
        self.ami_a.sendMessage(originate_msg)
        LOGGER.info("Placed call from Asterisk A to Bob")
        self.state = BOB_CALLED


def bob_registered(test_object, dummy):
    transfer = Transfer(test_object)
    transfer.call_bob()

