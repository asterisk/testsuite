#!/usr/bin/env python
"""Module that manipulates test state as a state machine

Note that this module has been superceded by the pluggable
test configuration framework and the apptest module.

Copyright (C) 2011, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging

LOGGER = logging.getLogger(__name__)


def print_test_event(event):
    """Log a test event

    Keyword Arguments:
    event    The TestEvent
    """
    LOGGER.debug("Test Event received:")
    for key, value in event.items():
        LOGGER.debug("\t" + key + "\t=\t" + value)


class TestStateController(object):
    """The controller for the TestEvent state machine"""

    def __init__(self, test_case, ami_receiver):
        """Constructor

        Keyword Arguments:
        test_case       The TestCase derived class that owns this controller
        ami_receiver    The AMI instance that will send the controller TestEvent
                        notifications
        """
        self._test_case = test_case
        self._current_state = None
        self._assert_handler = None

        # Register for TestEvent updates
        ami_receiver.registerEvent('TestEvent', self.handle_test_event)

    def handle_test_event(self, ami, event):
        """Handler for a TestEvent

        Keyword Arguments:
        ami     The AMI instance that sent us the TestEvent
        event   The TestEvent
        """
        print_test_event(event)

        if event['type'] == 'StateChange':
            if (self._current_state is not None):
                self._current_state.handle_state_change(ami, event)
            else:
                LOGGER.error("No initial state set before TestEvent received")
                self._current_state = FailureTestState(self)
        elif event['type'] == 'Assert':
            if (self._assert_handler is not None):
                self._assert_handler(ami, event)
            else:
                LOGGER.warn("ASSERT received but no handler defined; "
                            "test will now fail")
                self.fail_test()

    def change_state(self, test_state):
        """Change the current state machine state to a new state

        Keyword Arguments:
        test_state   The TestState to change to
        """
        self._current_state = test_state

    def fail_test(self):
        """
        Fail and stop the test
        """
        LOGGER.info("Setting test state to Fail")
        self._test_case.passed = False

        LOGGER.info("Stopping reactor")
        self._test_case.stop_reactor()

    def add_assert_handler(self, assert_handler_func):
        """Add an assert handler for Assert TestEvent types

        Keyword Arguments:
        assert_handler_func   The handler function that takes in an AMI instance
                              and an event instance and receives the Asserts

        Note that without a handler function, receiving any assert will
        automatically fail a test
        """
        self._assert_handler = assert_handler_func


class TestState(object):
    """Base class for the TestEvent state machine objects"""

    def __init__(self, controller):
        """Constructor

        Keyword Arguments:
        controller  The TestStateController instance
        """
        self.controller = controller

        if (self.controller is None):
            LOGGER.error("Controller is none")
            raise RuntimeError('Controller is none')

    def handle_state_change(self, ami, event):
        """Handle a state change.

        Called whenever a state change is received by the TestStateController.
        Concrete implementations should override this method and use it to
        change the state of the test by calling the change_state method

        Keyword Arguments:
        ami     The instance of AMI that sent us the TestEvent
        event   The TestEvent object
        """
        pass

    def change_state(self, new_state):
        """Inform the TestStateController that the test state needs to change

        Keyword Arguments:
        new_state    The new TestState to change to
        """
        self.controller.change_state(new_state)


class FailureTestState(TestState):
    """A generic failure state.

    Once transitioned to, the test will automatically fail.  No further
    state changes will be processed.
    """

    def __init__(self, controller):
        """Constructor

        Keyword Arguments:
        controller  The TestStateController instance
        """
        super(FailureTestState, self).__init__(controller)
        controller.fail_test()

    def handle_state_change(self, ami, event):
        """Handle a state change.

        This class ignores all subsequent state changes.

        Keyword Arguments:
        ami     The instance of AMI that sent us the TestEvent
        event   The TestEvent object
        """
        pass

    def change_state(self, new_state):
        """Inform the TestStateController that the test state needs to change

        This class ignores all changes of state.

        Keyword Arguments:
        new_state    The new TestState to change to
        """
        return
