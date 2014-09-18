#!/usr/bin/env python

import time
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

# This state is entered after the SUBSCRIBE-NOTIFY exchange for subscription
# refresh has occurred.
REFRESHED = 4

# This state is entered after Bob's MWI NOTIFY has been received.
BOB_STATE = 5

# This state is entered after SUBSCRIBE-NOTIFY exchange to terminate
# subscription has occurred.
TERMINATED = 6


class TestDriver(object):
    def __init__(self, module_config, test_object):
        self.ami = None
        self.state = UNESTABLISHED
        self.test_object = test_object
        self.alice_time = 0.0
        self.bob_time = 0.0
        test_object.register_ami_observer(self.ami_connect)

    def fail_test(self):
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()

    def ami_connect(self, ami):
        self.ami = ami
        self.ami.registerEvent('TestEvent', self.on_test_event)

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
        self.alice_time = time.time()
        message = {
            'Action': 'MWIUpdate',
            'Mailbox': 'alice',
            'NewMessages': '1',
            'OldMessages': '0',
        }
        self.ami.sendMessage(message)

    def on_subscription_state_change(self):
        if self.state != ESTABLISHED and self.state != REFRESHED:
            LOGGER.error("Unexpected state change from {0}. Expected state "
                         "{1} or {2}".format(self.state, ESTABLISHED,
                                             REFRESHED))
            self.fail_test()

        if self.state == ESTABLISHED:
            interval = time.time() - self.alice_time
            if interval < 5.0:
                LOGGER.error("Interval {0} too brief".format(interval))
                self.fail_test()
            LOGGER.debug("State change to {0}".format(ALICE_STATE))
            self.state = ALICE_STATE
        if self.state == REFRESHED:
            interval = time.time() - self.bob_time
            if time.time() - self.bob_time < 5.0:
                LOGGER.error("Interval {0} too brief".format(interval))
                self.fail_test()
            LOGGER.debug("State change to {0}".format(BOB_STATE))
            self.state = BOB_STATE

    def on_subscription_refreshed(self):
        if self.state != ALICE_STATE:
            LOGGER.error("Unexpected state change from {0}. Expected state "
                         "{1}".format(self.state, ALICE_STATE))
            self.fail_test()

        LOGGER.debug("State change to {0}".format(REFRESHED))
        self.state = REFRESHED
        self.bob_time = time.time()
        message = {
            'Action': 'MWIUpdate',
            'Mailbox': 'bob',
            'NewMessages': '1',
            'OldMessages': '0',
        }
        self.ami.sendMessage(message)

    def on_subscription_terminated(self):
        if self.state != BOB_STATE:
            LOGGER.error("Unexpected state change from {0}. Expected state "
                         "{1}".format(self.state, BOB_STATE))
            self.fail_test()

        LOGGER.debug("State change to {0}".format(TERMINATED))
        self.state = TERMINATED
        # If we've made it here, then the test has passed!
        self.test_object.set_passed(True)
        self.test_object.stop_reactor()
