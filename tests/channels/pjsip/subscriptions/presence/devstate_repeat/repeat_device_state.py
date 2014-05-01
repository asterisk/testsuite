#!/usr/bin/env python
'''
Copyright (C) 2014, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''


class RepeatDeviceState(object):
    def __init__(self, module_config, test_object):
        self.ami = None
        test_object.register_ami_observer(self.ami_connect)
        test_object.register_scenario_started_observer(self.scenario_started)

    def ami_connect(self, ami):
        self.ami = ami

    def scenario_started(self, scenario):
        # Device state defaults to NOT_INUSE. Repeat the same state now.
        message = {
            'Action': 'SetVar',
            'Variable': 'DEVICE_STATE(Custom:Eggs)',
            'Value': 'NOT_INUSE'
        }
        self.ami.sendMessage(message)
