#!/usr/bin/env python
'''
Copyright (C) 2011, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging

logger = logging.getLogger(__name__)

class TestStateController(object):
    """
    The controller for the TestEvent state machine
    """

    def __init__(self, testCase, amiReceiver):
        """
        testCase       The TestCase derived class that owns this controller
        amiReceiver    The AMI instance that will send the controller TestEvent notifications
        """
        self.__testCase = testCase
        self.__currentState = None
        self.__assertHandler = None

        """ Register for TestEvent updates """
        amiReceiver.registerEvent('TestEvent', self.handleTestEvent)

    def printTestEvent(self, event):
        """
        Print out a test event

        event    The TestEvent
        """
        logger.debug(" Test Event received:")
        for k, v in event.items():
            logger.debug("\t" + k + "\t=\t" + v)

    def handleTestEvent(self, ami, event):
        """
        Handler for a TestEvent

        ami     The AMI instance that sent us the TestEvent
        event   The TestEvent
        """
        if (logger.getEffectiveLevel() == logging.DEBUG):
            self.printTestEvent(event)

        if event['type'] == 'StateChange':
            if (self.__currentState != None):
                self.__currentState.handleStateChange(ami, event)
            else:
                logger.error("no initial state set before TestEvent received")
                self.__currentState = FailureTestState(self)
        elif event['type'] == 'Assert':
            if (self.__assertHandler != None):
                self.__assertHandler(ami, event)
            else:
                logger.warn("ASSERT received but no handler defined; test will now fail")
                self.failTest()

    def changeState(self, testState):
        """
        Change the current state machine state to a new state

        testState   The TestState to change to
        """
        self.__currentState = testState

    def failTest(self):
        """
        Fail and stop the test
        """
        logger.info("Setting test state to Fail")
        self.__testCase.passed = False

        logger.info("Stopping reactor")
        self.__testCase.stop_reactor()

    def addAssertHandler(self, assertHandlerFunc):
        """
        Add an assert handler for Assert TestEvent types

        assertHandlerFunc   The handler function that takes in an AMI instance and an event instance and
            receives the Asserts

        Note that without a handler function, receiving any assert will automatically fail a test
        """
        self.__assertHandler = assertHandlerFunc


class TestState(object):
    """
    Base class for the TestEvent state machine objects
    """

    def __init__(self, controller):
        """
        controller  The TestStateController instance
        """
        self.controller = controller

        if (self.controller == None):
            logger.error("Controller is none")
            raise RuntimeError('Controller is none')

    def handleStateChange(self, ami, event):
        """
        Handle a state change.  Called whenever a state change is received by the TestStateController.
        Concrete implementations should override this method and use it to change the state of the
        test by calling the changeState method

        ami     The instance of AMI that sent us the TestEvent
        event   The TestEvent object
        """
        pass

    def changeState(self, newState):
        """
        Inform the TestStateController that the test state needs to change

        newState    The new TestState to change to
        """
        self.controller.changeState(newState)

class FailureTestState(TestState):
    """
    A generic failure state.  Once transitioned to, the test will automatically fail.  No further
    state changes will be processed.
    """

    def __init__(self, controller):
        TestState(controller)
        controller.failTest()

    def handleStateChange(self, ami, event):
        pass

    def changeState(self, newState):
        return


