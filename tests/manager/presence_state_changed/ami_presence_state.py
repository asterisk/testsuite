#!/usr/bin/env python
'''
Copyright (C) 2014, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging
from asterisk.test_case import TestCase

LOGGER = logging.getLogger(__name__)

STATES = [
    {'status': 'unavailable', 'subtype': 'scrambled', 'message': 'breakfast'},
    {'status': 'available', 'subtype': 'fried', 'message': 'brunch'},
    {'status': 'away', 'subtype': 'poached', 'message': 'lunch'},
    {'status': 'xa', 'subtype': 'meringue', 'message': 'snack'},
    {'status': 'chat', 'subtype': 'custard', 'message': 'dinner'},
    {'status': 'dnd', 'subtype': 'souffle', 'message': 'dessert'},
]


class AMIPresenceState(TestCase):
    def __init__(self, path=None, config=None):
        super(AMIPresenceState, self).__init__(path, config)
        self.create_asterisk()
        self.state_pos = 0

    def run(self):
        super(AMIPresenceState, self).run()
        self.create_ami_factory()

    def check_parameter(self, event, parameter):
        actual = event.get(parameter)
        expected = STATES[self.state_pos][parameter]
        if actual != expected:
            LOGGER.error("Unexpected {0} received. Expected {1} but got \
                         {2}".format(parameter, expected, actual))
            self.set_passed(False)
            self.stop_reactor()

    def presence_state_event(self, ami, event):
        if event.get('presentity') != 'CustomPresence:Eggs':
            return

        self.check_parameter(event, 'status')
        self.check_parameter(event, 'subtype')
        self.check_parameter(event, 'message')

        self.state_pos += 1
        if self.state_pos >= len(STATES):
            self.set_passed(True)
            self.stop_reactor()

    def ami_connect(self, ami):
        ami.registerEvent('PresenceStateChange', self.presence_state_event)
        for state in STATES:
            status = state['status']
            subtype = state['subtype']
            message = state['message']

            ami_message = {
                'Action': 'SetVar',
                'Variable': 'PRESENCE_STATE(CustomPresence:Eggs)',
                'Value': "{0},{1},{2}".format(status, subtype, message)
            }
            ami.sendMessage(ami_message)
