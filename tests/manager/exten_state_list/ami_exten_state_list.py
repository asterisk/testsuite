#!/usr/bin/env python
"""
Copyright (C) 2014, Digium, Inc.
Mark Michelson <mmichelson@digium.com>
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
from twisted.internet import defer

LOGGER = logging.getLogger(__name__)

DEVICE_STATES = [
    {'device': 'ham', 'state': 'INVALID'},
    {'device': 'eggs', 'state': 'INUSE',},
]

PRESENCE_STATES = [
    {'presence': 'eggs', 'status': 'away', 'subtype': 'green', 'message': 'breakfast'},
    {'presence': 'ham', 'status': 'available', 'subtype': 'virginia', 'message': 'breakfast'},
]

EXPECTED_STATES = [
    {'status': '1', 'exten': 'eggs', 'statustext': 'InUse'},
    {'status': '4', 'exten': 'ham', 'statustext': 'Unavailable'}
]

class AMIExtensionStateList(object):
    """Pluggable module for listing out extension state"""

    def __init__(self, module_config, test_object):
        """Constructor

        Keyword Arguments:
        module_config The configuration for this object
        test_object   Our one and only test object
        """
        super(AMIExtensionStateList, self).__init__()

        self.received_events = []
        self.test_object = test_object
        self.received_expected_states = []
        self.exten_state_changes = 0
        self.presence_state_changes = 0

        self.list_complete_token = self.test_object.create_fail_token(
            'ExtensionStateListComplete event received')

        self.test_object.register_ami_observer(self.ami_connect_handler)

    def on_extension_status(self, ami, event):
        '''Event callback for ExtensionStatus

        ExtensionStatus events can happen either because we have requested an
        ExtensionStateList or because the extension state of an extension has
        changed. For our purposes, we are only concerned with the latter case.
        We can tell the cases apart by checking for the presence of an actionid
        on the event.
        '''
        if 'actionid' in event:
            return

        self.exten_state_changes += 1
        self.execute_query(ami)

    def on_presence_state_change(self, ami, event):
        '''Event callback for PresenceStatus

        We do not care about the contents of the event, just the fact that the
        event occurred.
        '''
        self.presence_state_changes += 1
        self.execute_query(ami)

    def execute_query(self, ami):
        """Called when all presence state values are set

        Keyword Arguments:
        ami The AMIProtocol object
        """

        if (self.exten_state_changes != len(DEVICE_STATES) or
            self.presence_state_changes != len(PRESENCE_STATES)):
            return

        deferred = ami.collectDeferred({'Action': 'ExtensionStateList'},
                                       'ExtensionStateListComplete')
        deferred.addCallbacks(self.extension_state_list_success,
                              self.action_failed)

    def action_failed(self, result):
        """Called if the AMI action failed

        Keyword Arguments:
        result The result of all of the AMI actions or a single action.
        """
        LOGGER.error("An action failed with result: %s" % str(result))
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()

    def ami_connect_handler(self, ami):
        """Handle AMI connection from the test object

        Keyword Arguments:
        ami The AMIProtocol instance that just connected
        """

        ami.registerEvent('ExtensionStatus', self.on_extension_status)
        ami.registerEvent('PresenceStateChange', self.on_presence_state_change)

        # Create a few state values
        resp_list = []
        for state in DEVICE_STATES:
            device = "DEVICE_STATE(Custom:{0})".format(state['device'])
            deferred = ami.setVar(None, device, state['state'])
            resp_list.append(deferred)
        for state in PRESENCE_STATES:
            presence = "PRESENCE_STATE(CustomPresence:{0})".format(state['presence'])
            value = "{0},{1},{2}".format(state['status'],
                                         state['subtype'],
                                         state['message'])
            deferred = ami.setVar(None, presence, value)
            resp_list.append(deferred)

        defer_list = defer.DeferredList(resp_list)
        defer_list.addErrback(self.action_failed)

    def extension_state_list_success(self, result):
        """Handle the completion of the ExtensionStateList action

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
            self.handle_exten_status_event(list_event)

        self.test_object.remove_fail_token(self.list_complete_token)
        self.test_object.stop_reactor()

    def find_matching_expected_state(self, event):
        """Find an expected state that matches the current event

        Keyword Arguments:
        event The ExtensionStatus event

        Returns:
        The matching expected state dictionary, or None if no match found
        """
        for expected_state in EXPECTED_STATES:
            if expected_state not in self.received_expected_states:
                if (expected_state['exten'] == event.get('exten') and
                    expected_state['status'] == event.get('status') and
                    expected_state['statustext'] == event.get('statustext')):
                    return expected_state
        return None

    def handle_exten_status_event(self, event):
        if 'actionid' not in event:
            # Not for us!
            return

        if (event.get('event') != 'ExtensionStatus'):
            # Ignore completion event
            return

        matching_state = self.find_matching_expected_state(event)
        if matching_state is None:
            LOGGER.error("Received unexpected or duplicate event: %s" % str(event))
            self.test_object.set_passed(False)
            return

        self.received_expected_states.append(matching_state)

        if len(self.received_expected_states) == len(EXPECTED_STATES):
            self.test_object.set_passed(True)

