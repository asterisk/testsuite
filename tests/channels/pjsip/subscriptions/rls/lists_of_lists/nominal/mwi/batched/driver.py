#!/usr/bin/env python

import logging

LOGGER = logging.getLogger(__name__)

# These are the states that are moved through during the tests. They are listed
# here in the order that they occur throughout the test.

# Initial state before subscription establishment.
UNESTABLISHED = 1

# This state is entered after initial SUBSCRIBE-NOTIFY exchange has occurred.
ESTABLISHED = 2

# This state is entered after Alice's MWI NOTIFY has been received.
ALICE_STATE = 3

# This state is entered after Bob's MWI NOTIFY has been received.
BOB_STATE = 4


class TestDriver(object):
    def __init__(self, module_config, test_object):
        self.ami = None
        self.state = UNESTABLISHED
        self.test_object = test_object
        self.scenario_completed = False
        test_object.register_ami_observer(self.ami_connect)
        test_object.register_scenario_stopped_observer(self.scenario_complete)

    def fail_test(self):
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()

    def ami_connect(self, ami):
        self.ami = ami
        self.ami.registerEvent('TestEvent', self.on_test_event)

    def scenario_complete(self, scenario):
        if self.state != BOB_STATE:
            LOGGER.error("Test ended on unexpected state {0}".format(self.state))
            self.fail_test()

        self.scenario_completed = True

    def on_test_event(self, ami, event):
        state = event['state']
        if state == 'SUBSCRIPTION_ESTABLISHED':
            self.on_subscription_established()
        elif state == 'SUBSCRIPTION_REFRESHED':
            self.on_subscription_refreshed()
        elif state == 'SUBSCRIPTION_TERMINATED':
            self.on_subscription_terminated()
        elif state == 'SUBSCRIPTION_STATE_CHANGED':
            self.on_subscription_state_change()

    def on_subscription_established(self):
        if self.state != UNESTABLISHED:
            LOGGER.error("Unexpected state change from {0}. Expected state "
                         "{1}".format(self.state, UNESTABLISHED))
            self.fail_test()

        LOGGER.debug("State change to {0}".format(ESTABLISHED))
        self.state = ESTABLISHED
        message = {
            'Action': 'MWIUpdate',
            'Mailbox': 'alice',
            'NewMessages': '1',
            'OldMessages': '0'
        }
        self.ami.sendMessage(message)
        message['Mailbox'] = 'bob'
        self.ami.sendMessage(message)

    def on_subscription_state_change(self):
        if self.state == ESTABLISHED:
            self.state = ALICE_STATE
            LOGGER.debug("State change to {0}".format(ALICE_STATE))
        elif self.state == ALICE_STATE:
            self.state = BOB_STATE
            LOGGER.debug("State change to {0}".format(BOB_STATE))
        else:
            LOGGER.error("Unexpected state change from {0}. Expected state "
                         "{1} or {2}".format(self.state, ESTABLISHED,
                                             ALICE_STATE))
            self.fail_test()

    def on_subscription_refreshed(self):
        LOGGER.error("Unexpected resubscription")
        self.fail_test()

    def on_subscription_terminated(self):
        # Asterisk will send a termination NOTIFY on shutdown. As long as this
        # happens after the scenario completes, it's fine.
        if self.scenario_completed:
            return

        LOGGER.error("Unexpected subscription termination")
        self.fail_test()
