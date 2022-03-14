#!/usr/bin/env python
"""
Copyright (C) 2015, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import time
import logging

LOGGER = logging.getLogger(__name__)

# These are the states that are moved through during the tests. They are listed
# here in the order that they occur throughout the test.

# Initial state before subscription establishment.
UNESTABLISHED = 1

# This state is entered after initial SUBSCRIBE-NOTIFY exchange has occurred.
ESTABLISHED = 2

# This state is entered after Alice's device state NOTIFY has been received.
ALICE_STATE = 3

# This state is entered after the SUBSCRIBE-NOTIFY exchange for subscription
# refresh has occurred.
REFRESHED = 4

# This state is entered after Bob's device state NOTIFY has been received.
BOB_STATE = 5

def named_constant_to_text(state):
    """Converts a named state constant to textual representation.

    Keyword Arguments:
    state                      -- The named state constant.

    Returns:
    A string representing the named constant.
    """

    if state == UNESTABLISHED:
        return 'UNESTABLISHED'
    elif state == ESTABLISHED:
        return 'ESTABLISHED'
    elif state == ALICE_STATE:
        return 'ALICE_STATE'
    elif state == REFRESHED:
        return 'REFRESHED'
    elif state == BOB_STATE:
        return 'BOB_STATE'
    return 'UNKNOWN'

def build_users_list():
    """Builds the list of users.

    Returns:
    A list of TestUser objects.
    """

    users = list()

    for info in [('Alice', ESTABLISHED), ('Bob', REFRESHED)]:
        name = info[0]
        user = TestUser(name,
                        info[1],
                        globals()[name.upper() + '_STATE'])
        users.append(user)
    return users


class TestUser(object):
    """A test user.

    This class is responsbile for keeping track of the start/end states,
    transition time interval, and current state for a SipPScenario actor.
    """

    def __init__(self, name, start_state, end_state):
        """Constructor.

        Keyword Arguments:
        name                   -- The name for this TestUser instance
        start_state            -- The state to use when this user is activated.
        end_state              -- The state to use when this user is
                                  deactivated.
        """

        self.name = name
        self.state = UNESTABLISHED
        self.__start_state = start_state
        self.__end_state = end_state
        self.__start_time = 0.0
        self.__end_time = 0.0

    def activate(self, ami):
        """Activates this TestUser.

        This will update the state of the user to the start_state and send an
        AMI message which triggers the SipPScenario to transition its state."""

        message = "Activating user: {0}."
        LOGGER.debug(message.format(self.name))

        self.state = self.__start_state
        self.__start_time = time.time()

        ami_message = {
            'Action': 'SetVar',
            'Variable': 'DEVICE_STATE(Custom:{0})'.format(self.name.lower()),
            'Value': 'InUse'
        }
        ami.sendMessage(ami_message)

    def deactivate(self):
        """Deactivates this TestUser."""

        message = "Deactivating user: {0}."
        LOGGER.debug(message.format(self.name))

        self.state = self.__end_state
        self.__end_time = time.time()

    def check_elapsed_time(self):
        """Checks the elapsed between acitvation and deactivation."""

        message = "Checking time interval for {0}."
        LOGGER.debug(message.format(self.name))

        message = "Time interval for {0}: {1}. Check {2}."
        interval = self.__end_time - self.__start_time
        if interval < 5.0:
            LOGGER.error(message.format(self.name, interval, "failed"))
            return False

        LOGGER.debug(message.format(self.name, interval, "passed"))
        return True


class TestDriver(object):
    """The driver for the test.

    This class is responsbile for initiating the state changes for the
    SipPScenario actors.
    """

    def __init__(self, module_config, test_object):
        """Constructor.

        Keyword Arguments:
        module_config          -- The YAML configuration for this test.
        test_object            -- The TestCaseModule instance for this test.
        """

        self.ami = None
        self.test_object = test_object

        self.__current_user = None
        self.__users = build_users_list()
        self.__iterator = iter(self.__users)

        test_object.register_ami_observer(self.on_ami_connect)

    def check_state(self, valid_states):
        """Checks the state of the test.

        Keyword Arguments:
        valid_states           -- A list of states that are valid.

        Returns:
        True if the test state matches at least one of the valid states.
        Otherwise, returns False.
        """

        current_state = self.get_state()
        message = "Checking that the test state: {0} is valid."
        LOGGER.debug(message.format(current_state))

        for state in valid_states:
            if state == current_state:
                LOGGER.debug("Test state is valid.")
                return True

        states = \
            ', or '.join([named_constant_to_text(x) for x in valid_states])
        LOGGER.error("Unexpected test state. Expected: {0}.".format(states))
        return False

    def fail_test(self):
        """Fails the test."""

        LOGGER.error("Failing the test.")
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()

    def get_state(self):
        """Gets the test state.

        Returns:
        If the current user is None, this will return UNESTABLISHED. Otherwise,
        the state of the current user is returned.
        """

        if self.__current_user is None:
            return UNESTABLISHED

        return self.__current_user.state

    def log_state(self, caller):
        """Logs the state of the test for a given caller.

        Keyword Arguments:
        caller                 -- The caller requesting the state to be logged.
        """

        message = "In {0}. self.state={1}."
        LOGGER.debug(message.format(caller.__name__,
                                    named_constant_to_text(self.get_state())))

    def on_ami_connect(self, ami):
        """Handles the AMI connect event.

        Keyword Arguments:
        ami                    -- The AMI instance that raised this event.
        """

        self.ami = ami
        self.ami.registerEvent('TestEvent', self.on_ami_test_event)

    def on_ami_test_event(self, ami, event):
        """Handles an AMI TestEvent.

        Routes the test data according to the state of the AMI event.

        Keyword Arguments:
        sender                 -- The ami instance that raised the event.
        event                  -- The event payload.
        """

        state = event['state']
        message = "In self.on_test_event. event[state]={0}."
        LOGGER.debug(message.format(state))

        if state == 'SUBSCRIPTION_ESTABLISHED':
            self.on_subscription_established()
        elif state == 'SUBSCRIPTION_REFRESHED':
            self.on_subscription_refreshed()
        elif state == 'SUBSCRIPTION_TERMINATED':
            self.on_subscription_terminated()
        elif state == 'SUBSCRIPTION_STATE_CHANGED':
            self.on_subscription_state_changed()

    def on_subscription_established(self):
        """Handles an AMI 'SUBSCRIPTION_ESTABLISHED' TestEvent.

        Verifies the current state matches the expected state and transitions
        the TestUser.
        """

        self.log_state(self.on_subscription_established)
        if not self.check_state([UNESTABLISHED]):
            self.fail_test()
        self.transition_user()

    def on_subscription_refreshed(self):
        """Handles an AMI 'SUBSCRIPTION_REFRESHED' TestEvent.

        Verifies the current state matches the expected state and transitions
        the TestUser.
        """

        self.log_state(self.on_subscription_refreshed)
        if not self.check_state([ALICE_STATE]):
            self.fail_test()
        self.transition_user()

    def on_subscription_state_changed(self):
        """Handles an AMI 'SUBSCRIPTION_STATE_CHANGED' TestEvent.

        Deactivates the current user and verifies that its time inteval
        is greater than the tolerance level (5 seconds).
        """

        self.log_state(self.on_subscription_state_changed)
        if not self.check_state([ESTABLISHED, REFRESHED]):
            self.fail_test()

        self.__current_user.deactivate()
        if not self.__current_user.check_elapsed_time():
            self.fail_test()

    def on_subscription_terminated(self):
        """Handles an AMI SUBSCRIPTION_TERMINATED TestEvent.

        Verifies that the final state matches the expected state (BOB_STATE)
        and marks the test as passed or failed."""

        self.log_state(self.on_subscription_terminated)
        if not self.check_state([BOB_STATE]):
            self.fail_test()

        # If we've made it here, then the test has passed!
        self.test_object.set_passed(True)
        self.test_object.stop_reactor()

    def transition_user(self):
        """ Transitions the current user to the next user in the list.

        This will set the value of current_user to the next available user in
        the list, or None, if we are at the end of the list. If we are at the
        end of the list, nothing else is done. Otherwise, the current_user is
        activated.
        """

        try:
            self.__current_user = self.__iterator.__next__()
        except StopIteration:
            self.__current_user = None
            return

        self.__current_user.activate(self.ami)
