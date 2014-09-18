#!/usr/bin/env python

import logging

LOGGER = logging.getLogger(__name__)

# These are the states that are moved through during the tests. They are listed
# here in the order that they occur throughout the test.

# Initial state before subscription establishment.
UNESTABLISHED = 1

# This state is entered after initial SUBSCRIBE-NOTIFY exchange has occurred.
ESTABLISHED = 2

# This state is entered after the SUBSCRIBE-NOTIFY exchange for subscription
# refresh has occurred.
REFRESHED = 3


class TestDriver(object):
    def __init__(self, module_config, test_object):
        self.ami = None
        self.state = UNESTABLISHED
        self.test_object = test_object
        self.test_object.register_ami_observer(self.ami_connect)
        self.test_object.register_scenario_stopped_observer(
            self.on_scenario_complete)

    def fail_test(self):
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()

    def pass_test(self):
        self.test_object.set_passed(True)
        self.test_object.stop_reactor()

    def on_scenario_complete(self, result):
        if not result.passed:
            LOGGER.error("SIPp scenario failed")
            self.fail_test()

        if self.state != REFRESHED:
            LOGGER.error("SIPp scenario finished with test in unexpected "
                         "state. Expected {0} but was in {1}".format(
                             REFRESHED, self.state))
            self.fail_test()

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
        message = {
            'Action': 'SetVar',
            'Variable': 'DEVICE_STATE(Custom:alice)',
            'Value': 'InUse'
        }
        self.ami.sendMessage(message)

    def on_subscription_state_change(self):
        LOGGER.error("Unexpected state change NOTIFY received")
        self.fail_test()

    def on_subscription_refreshed(self):
        if self.state != ESTABLISHED:
            LOGGER.error("Unexpected state change from {0}. Expected state "
                         "{1}".format(self.state, ESTABLISHED))
            self.fail_test()

        LOGGER.debug("State change to {0}".format(REFRESHED))
        self.state = REFRESHED

    def on_subscription_terminated(self):
        LOGGER.error("Unexpected subscription termination received")
        self.fail_test()
