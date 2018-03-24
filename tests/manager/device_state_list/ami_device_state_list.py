#!/usr/bin/env python
"""
Copyright (C) 2014, Digium, Inc.
Mark Michelson <mmichelson@digium.com>
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
from asterisk.test_case import TestCase
from twisted.internet import defer

LOGGER = logging.getLogger(__name__)

STATES = [
    {'device': 'Ham', 'state': 'INVALID'},
    {'device': 'Eggs', 'state': 'INUSE',},
]

class AMIDeviceStateList(object):
    """Pluggable module for listing out device states"""

    def __init__(self, module_config, test_object):
        """Constructor

        Keyword Arguments:
        module_config The configuration for this object
        test_object   Our one and only test object
        """
        super(AMIDeviceStateList, self).__init__()

        self.received_events = []
        self.test_object = test_object
        self.state_pos = 0

        self.list_complete_token = self.test_object.create_fail_token(
            'DeviceStateListComplete event received')

        self.test_object.register_ami_observer(self.ami_connect_handler)

    def ami_connect_handler(self, ami):
        """Handle AMI connection from the test object

        Keyword Arguments:
        ami The AMIProtocol instance that just connected
        """

        def _action_failed(result):
            """Called if the AMI action failed

            Keyword Arguments:
            result The result of all of the AMI actions or a single action.
            """
            LOGGER.error("An action failed with result: %s" % str(result))
            self.test_object.set_passed(False)
            self.test_object.stop_reactor()

        def _execute_query(result, ami):
            """Called when all device state values are set

            Keyword Arguments:
            result The result of all of the deferreds
            ami The AMIProtocol object
            """

            deferred = ami.collectDeferred({'Action': 'DeviceStateList'},
                                           'DeviceStateListComplete')
            deferred.addCallbacks(self.device_state_list_success,
                                  _action_failed)

        # Create a few device state values
        resp_list = []
        for state in STATES:
            device = "DEVICE_STATE(Custom:{0})".format(state['device'])
            deferred = ami.setVar(None, device, state['state'])
            resp_list.append(deferred)

        defer_list = defer.DeferredList(resp_list)
        defer_list.addCallback(_execute_query, ami)
        defer_list.addErrback(_action_failed)

    def device_state_list_success(self, result):
        """Handle the completion of the DeviceStateList action

        Keyword Arguments:
        result The list ack and list elements (does not include the completion event)
        """

        list_ack = result[0]
        if list_ack.get('response') != 'Success':
            LOGGER.error("Failed to get 'success' response for action")
            self.test_object.set_passed(False)
        if list_ack.get('eventlist') != 'start':
            LOGGER.error("Failed to get 'start' notification for action")
            self.test_object.set_passed(False)

        list_events = result[1:]
        for list_event in list_events:
            self.handle_device_state_event(list_event)

        self.test_object.remove_fail_token(self.list_complete_token)
        self.test_object.stop_reactor()

    def check_parameter(self, event, parameter):
        """Verify a parameter from a DeviceStateChange event

        Keyword Arguments:
        event     The DeviceStateChange event
        parameter The parameter in the event to verify
        """
        actual = event.get(parameter)
        expected = STATES[self.state_pos][parameter]
        if actual != expected:
            LOGGER.error("Unexpected {0} received. Expected {1} but got \
                         {2}".format(parameter, expected, actual))
            self.test_object.set_passed(False)

    def handle_device_state_event(self, event):
        if 'actionid' not in event:
            # Not for us!
            return

        if event.get('device') not in ['Custom:%s' % state['device']
                                        for state in STATES]:
            # Not a device we care about
            return

        self.check_parameter(event, 'state')

        self.state_pos += 1
        if self.state_pos == len(STATES):
            self.test_object.set_passed(True)
        elif self.state_pos > len(STATES):
            LOGGER.error("Oh snap, we got %d device state updates but expected %d" %
                (self.state_pos, len(STATES)))
            self.test_object.set_passed(False)

