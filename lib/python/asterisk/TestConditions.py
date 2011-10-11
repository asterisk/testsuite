#!/usr/bin/env python
'''
Copyright (C) 2011, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging
import logging.config

from buildoptions import AsteriskBuildOptions
from TestConfig import TestConfig

logger = logging.getLogger(__name__)

def enum(**enums):
    return type('Enum', (), enums)

class TestConditionController(object):
    """
    This class manages the pre and post-test condition checking.  Pre and post-test
    conditions can be added to this controller and will be automatically called
    before and after a test runs.  Based on the pass / fail of the test, the test
    will be automatically stopped, halted, or otherwise affected.
    """

    def __init__(self, test_config, asterisk_instances = [], stop_test_callback = None):
        """
        Initialize the TestConditionController

        Keyword arguments:
        test_config -- the TestConfig object containing the configuration for this test
        asterisk_instances -- Predefined instances of Asterisk that already exist
        stop_test_callback -- The method to call when a test should be halted
        """
        self.__prechecks = []
        self.__postchecks = []
        self.__ast = asterisk_instances
        self.__stop_test_callback = stop_test_callback
        self.__observers = []
        self.register_observer(self.__handle_condition_failure, "Failed")
        self.register_observer(self.__handle_condition_failure, "Inconclusive")
        self.test_config = test_config

    def register_asterisk_instance(self, ast):
        """
        Registers an Asterisk instance with the controller.  All instances of
        Asterisk registered with the controller will be passed to the pre and post
        test condition objects for condition checking.

        Keyword arguments:
        ast -- The asterisk instance to register for pre/post test checks
        """
        self.__ast.append(ast)

    def register_pre_test_condition(self, pre_test_condition):
        """
        Register a pre-test conditional check.  These test conditions will be evaluated
        prior to execution of the main test body.

        Keyword arguments:
        pre_test_condition -- The pre-test condition to check
        """
        t = pre_test_condition, None
        self.__prechecks.append(t)

    def register_post_test_condition(self, post_test_condition, matching_pre_condition_name = ""):
        """
        Register a post-test conditional check.  These test conditions are evaluated after
        execution of the main test body.

        Keyword arguments:
        post_test_condition -- The post-test condition to check
        matching_pre_condition_name -- A matching pre-test condition name to be passed to the post-test condition
            during its evaluation

        Note: will throw ValueError if matching_pre_condition_name is specified and is not
        registered with the controller
        """
        matching_pre_condition = None
        if (matching_pre_condition_name != ""):
            for pre in self.__prechecks:
                if pre[0].getName() == matching_pre_condition_name:
                    matching_pre_condition = pre[0]
                    break;
            if (matching_pre_condition == None):
                errMsg = "No pre condition found matching %s" % matching_pre_condition_name
                raise ValueError(errMsg)
        t = post_test_condition, matching_pre_condition
        self.__postchecks.append(t)

    def register_observer(self, callback_method, filter=""):
        """
        Register an observer for the pre- and post-test condition checks.  An observer
        will be called if a pre or post-test condition check matches the passed in filter.
        If a filter is not provided, the observer will always be called.
        """
        t = callback_method, filter
        logger.debug("Registering: " + str(callback_method))
        self.__observers.append(t)

    def evaluate_pre_checks(self):
        """
        Evaluate the pre-test conditions
        """
        logger.debug("Evaluating pre checks")
        self.__evaluate_checks(self.__prechecks)

    def evaluate_post_checks(self):
        """
        Evaluate the post-test conditions
        """
        logger.debug("Evaluating post checks")
        self.__evaluate_checks(self.__postchecks)

    def __evaluate_checks(self, check_list):
        """ Register the instances of Asterisk and evaluate """
        for check in check_list:
            if (check[0].check_build_options()):
                for ast in self.__ast:
                    check[0].register_asterisk_instance(ast)
                if (check[0].getEnabled()):
                    logger.debug("Evaluating %s" % check[0].getName())
                    if (check[1] != None):
                        check[0].evaluate(check[1])
                    else:
                        check[0].evaluate()
                    self.__check_observers(check[0])

    def __check_observers(self, test_condition):
        for observerTuple in self.__observers:
            if (observerTuple[1] == "" or (observerTuple[1] != "" and observerTuple[1] == test_condition.getStatus())):
                observerTuple[0](test_condition)

        if test_condition.getStatus() == 'Failed' and self.__stop_test_callback != None:
            self.__stop_test_callback()

    def __handle_condition_failure(self, test_condition):
        if (test_condition.getStatus() == 'Inconclusive'):
            logger.warning(test_condition)
        elif (test_condition.getStatus() == 'Failed'):
            logger.info(str(test_condition.pass_expected))
            if test_condition.pass_expected:
                logger.error(test_condition)
            else:
                logger.warning(test_condition)

TestStatuses = enum(Inconclusive='Inconclusive', Failed='Failed', Passed='Passed')

class TestCondition(object):
    """
    The test condition base class.  This object provides the evaluate method signature
    which must be overriden, and various helper methods to print out and save the status
    of the test condition check
    """

    __buildOptions = AsteriskBuildOptions()

    def __init__(self, test_config):
        """
        Initialize a new test condition

        Keyword arguments:
        test_config - the test configuration object that defines this Test Condition
        """
        self.failureReasons = []
        self.__name = test_config.classTypeName
        self.__testStatus = TestStatuses.Inconclusive
        self.ast = []
        self.build_options = []
        self.__enabled = test_config.enabled
        self.pass_expected = test_config.passExpected

    def __str__(self):
        """
        Convert the object to a string representation
        """
        status = "Test Condition [%s]: [%s]" % (self.__name, self.__testStatus)
        if (self.__testStatus == TestStatuses.Failed):
            for reason in self.failureReasons:
                status += "\n\tReason: %s" % reason
        return status

    def check_build_options(self):
        """
        Checks the required Asterisk Build Options for this TestCondition.
        Returns true if all conditions are met, false if a condition was not met.
        """
        retVal = True
        for option in self.build_options:
            if not TestCondition.__buildOptions.checkOption(option[0], option[1]):
                logger.debug("Build option %s not set to %s; test condition [%s] will not be checked" % (option[0], option[1], self.__name))
                retVal = False
        return retVal

    def add_build_option(self, optionName, expectedValue="1"):
        """
        Adds a build option in Asterisk to check for before executing this condition.

        Keyword arguments:
        optionName -- The name of the Asterisk build option to check for
        expectedValue -- The value the build option must have in order for this condition to execute
        """
        o = optionName, expectedValue
        self.build_options.append(o)

    def register_asterisk_instance(self, ast):
        """
        Registers an instance of asterisk to be tested by this condition.  Note that
        you are guaranteed to have all instances of Asterisk that should be checked
        by the condition by the time the evaluate method is called.

        Keyword arguments:
        ast -- an instance of Asterisk to check
        """
        self.ast.append(ast)

    def evaluate(self, related_test_condition = None):
        """
        Evaluate the test condition

        Derived classes must implement this method and check their test condition
        here.  If the test condition passes they should call passCheck, otherwise they
        should call failCheck.

        Keyword arguments:
        related_test_condition -- A test condition object that is related to this one.  Provided if specified
            when this test condition is registered to the test condition controller.
        """
        pass

    def getEnabled(self):
        """
        True if the condition is enabled and should run, false otherwise
        """
        return self.__enabled

    def getName(self):
        """
        Return the name of the test condition
        """
        return self.__name

    def getStatus(self):
        """
        Return the current status of the test
        """
        return str(self.__testStatus)

    def passCheck(self):
        """
        Mark that the test condition has passed.  Note that this will not overwrite
        a previous indication that the test condition failed.
        """
        if (self.__testStatus == TestStatuses.Inconclusive):
            self.__testStatus = TestStatuses.Passed

    def failCheck(self, reason = ""):
        """
        Mark that the test condition has failed.  Note that the test condition cannot
        be changed once placed in this state.

        Keyword arguments:
        reason -- The reason the test failed
        """
        self.__testStatus = TestStatuses.Failed
        if (reason != ""):
            self.failureReasons.append(reason)


