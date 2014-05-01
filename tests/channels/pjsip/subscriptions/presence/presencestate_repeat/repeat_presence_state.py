#!/usr/bin/env python
'''
Copyright (C) 2014, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''


class RepeatPresenceState(object):
    def __init__(self, module_config, test_object):
        self.ami = None
        self.ami_message = {
            'Action': 'SetVar',
            'Variable': 'PRESENCE_STATE(CustomPresence:Eggs)',
            'Value': 'AWAY,scrambled,feeling a bit sick'
        }
        test_object.register_ami_observer(self.ami_connect)
        test_object.register_scenario_started_observer(self.scenario_started)

    def ami_connect(self, ami):
        self.ami = ami
        # Give ourselves an initial presence
        self.ami.sendMessage(self.ami_message)

    def scenario_started(self, scenario):
        # Now repeat the same presence state.
        self.ami.sendMessage(self.ami_message)
