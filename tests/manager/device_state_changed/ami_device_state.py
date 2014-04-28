#!/usr/bin/env python
'''
Copyright (C) 2014, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging
from test_case import TestCase

LOGGER = logging.getLogger(__name__)

STATES = [
    'NOT_INUSE',
    'INUSE',
    'BUSY',
    'INVALID',
    'UNAVAILABLE',
    'RINGING',
    'RINGINUSE',
]


class AMIDeviceState(TestCase):
    def __init__(self, path=None, config=None):
        super(AMIDeviceState, self).__init__(path, config)
        self.create_asterisk()
        self.state_pos = 0

    def run(self):
        super(AMIDeviceState, self).run()
        self.create_ami_factory()

    def device_state_event(self, ami, event):
        if event.get('device') != 'Custom:Eggs':
            return

        state = event.get('state')
        expected_state = STATES[self.state_pos]
        if state != expected_state:
            LOGGER.error("Unexpected state received. Expected {0} but got \
                         {1}".format(expected_state, state))
            self.set_passed(False)
            self.stop_reactor()

        self.state_pos += 1
        if self.state_pos >= len(STATES):
            self.set_passed(True)
            self.stop_reactor()

    def ami_connect(self, ami):
        ami.registerEvent('DeviceStateChange', self.device_state_event)
        for state in STATES:
            message = {
                'Action': 'SetVar',
                'Variable': 'DEVICE_STATE(Custom:Eggs)',
                'Value': state
            }
            ami.sendMessage(message)
