#!/usr/bin/env python
'''
Copyright (C) 2014, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

STATE = "AWAY"
SUBTYPE_1 = "scrambled"
MESSAGE_1 = "feeling a bit sick"
SUBTYPE_2 = "poached"
MESSAGE_2 = "the horses could not put me back together"

INIT_STATE = "{0},{1},{2}".format(STATE, SUBTYPE_1, MESSAGE_1)
NEW_SUBTYPE = "{0},{1},{2}".format(STATE, SUBTYPE_2, MESSAGE_1)
NEW_MESSAGE = "{0},{1},{2}".format(STATE, SUBTYPE_2, MESSAGE_2)

class RepeatPresenceState(object):
    def __init__(self, module_config, test_object):
        self.ami = None
        self.ami_message = {
            'Action': 'SetVar',
            'Variable': 'PRESENCE_STATE(CustomPresence:Eggs)',
            'Value': INIT_STATE
        }
        test_object.register_ami_observer(self.ami_connect)

    def ami_connect(self, ami):
        self.ami = ami
        self.ami.registerEvent('TestEvent', self.handle_sub_established)
        # Set initial presence state
        self.ami.sendMessage(self.ami_message)

    def handle_sub_established(self, ami, event):
        if event['state'] != 'SUBSCRIPTION_ESTABLISHED':
            return

        # Set new presence subvalues. These should result in SIP NOTIFYs
        self.ami_message['Value'] = NEW_SUBTYPE
        self.ami.sendMessage(self.ami_message)

        self.ami_message['Value'] = NEW_MESSAGE
        self.ami.sendMessage(self.ami_message)
