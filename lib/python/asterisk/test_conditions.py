#!/usr/bin/env python
"""Test condition framework

Test conditions are run before and after a test is run. They capture/verify the
internal state of Asterisk before a test runs, and check that the state of
Asterisk after a test has completed is acceptable or in an expected state.

The framework allows for modules to be written that verify different pieces
of functionality, and is responsible for calling the modules at the appropriate
times, setting the pass/fail status of the test, etc.

Copyright (C) 2011-2012, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
import logging.config

from buildoptions import AsteriskBuildOptions
from twisted.internet import defer

LOGGER = logging.getLogger(__name__)


def enum(**enums):
    """Make an enumeration out of the passed in values"""
    return type('Enum', (), enums)


def handle_condition_failure(test_condition):
    """Handle a failure in a test condition.

    This will generally fail the test, unless we expected a failure
    """
    if (test_condition.get_status() == 'Inconclusive'):
        LOGGER.warning(test_condition)
    elif (test_condition.get_status() == 'Failed'):
        LOGGER.info(str(test_condition.pass_expected))
        if test_condition.pass_expected:
            LOGGER.error(test_condition)
        else:
            LOGGER.warning(test_condition)


class TestConditionController(object):
    """Class that manages the pre and post-test condition checking.

    Pre and post-test conditions can be added to this controller and will be
    automatically called before and after a test runs. Based on the pass/fail of
    the test, the test will be automatically stopped, halted, or otherwise
    affected.
    """

    def __init__(self, test_config,
                 asterisk_instances=None,
                 stop_test_callback=None):
        """Initialize the TestConditionController

        Keyword arguments:
        test_config The TestConfig object containing the configuration for this test
        asterisk_instances Predefined instances of Asterisk that already exist
        stop_test_callback The method to call when a test should be halted
        """
        self._prechecks = []
        self._postchecks = []
        self._ast = asterisk_instances or []
        self._stop_test_callback = stop_test_callback
        self._observers = []
        self.register_observer(handle_condition_failure, "Failed")
        self.register_observer(handle_condition_failure, "Inconclusive")
        self.test_config = test_config

    def register_asterisk_instance(self, ast):
        """Register an Asterisk instance with the controller.

        All instances of Asterisk registered with the controller will be passed
        to the pre and post test condition objects for condition checking.

        Keyword arguments:
        ast The asterisk instance to register for pre/post test checks
        """
        self._ast.append(ast)

    def register_pre_test_condition(self, pre_test_condition):
        """Register a pre-test conditional check.

        These test conditions will be evaluated prior to execution of the main
        test body.

        Keyword arguments:
        pre_test_condition The pre-test condition to check
        """
        LOGGER.info('Registered pre test condition %s' % str(pre_test_condition))
        self._prechecks.append((pre_test_condition, None))

    def register_post_test_condition(self, post_test_condition,
                                     matching_pre_condition_name=""):
        """Register a post-test conditional check.

        These test conditions are evaluated after execution of the main test
        body.

        Keyword arguments:
        post_test_condition         The post-test condition to check
        matching_pre_condition_name A matching pre-test condition name to be
                                    passed to the post-test condition during its
                                    evaluation

        This will throw ValueError if matching_pre_condition_name is specified
        and is not registered with the controller
        """
        matching_pre_condition = None
        if (matching_pre_condition_name != ""):
            for pre in self._prechecks:
                if pre[0].get_name() == matching_pre_condition_name:
                    matching_pre_condition = pre[0]
                    break
            if (matching_pre_condition is None):
                err_msg = ("No pre condition found matching %s" %
                           matching_pre_condition_name)
                LOGGER.error(err_msg)
                return
        LOGGER.info('Registered post test condition %s' % str(post_test_condition))
        self._postchecks.append((post_test_condition, matching_pre_condition))

    def register_observer(self, callback_method, test_filter=""):
        """Register an observer for the pre- and post-test condition checks.

        An observer will be called if a pre or post-test condition check matches
        the passed in filter. If a filter is not provided, the observer will
        always be called.

        Keyword Arguments:
        callback_method The method to be called. The callback method should take
                        a single argument, the test condition object whose
                        execution completed.
        test_filter     The name of the test condition to look for. If empty,
                        all test conditions are passed.
        """
        LOGGER.debug("Registering: " + str(callback_method))
        self._observers.append((callback_method, test_filter))

    def evaluate_pre_checks(self):
        """
        Evaluate the pre-test conditions

        Returns:
        A deferred that will be raised when all pre-checks have finished,
        or None if no pre-checks exist
        """
        if (not self._prechecks):
            return None

        LOGGER.debug("Evaluating pre checks")
        finished_deferred = defer.Deferred()
        self.__evaluate_check(self._prechecks, 0, finished_deferred)
        return finished_deferred

    def evaluate_post_checks(self):
        """
        Evaluate the post-test conditions

        Returns:
        A deferred that will be raised when all post-checks have finished,
        or None if no post-checks exist
        """
        if (not self._postchecks):
            return None

        LOGGER.debug("Evaluating post checks")
        finished_deferred = defer.Deferred()
        self.__evaluate_check(self._postchecks, 0, finished_deferred)
        return finished_deferred

    def __evaluate_check(self, check_list, counter, finished_deferred):
        """ Register the instances of Asterisk and evaluate """

        def __evaluate_callback(result, params):
            """Called when a test condition finished successfully"""
            check_list, counter, finished_deferred = params
            self.__check_observers(result)
            counter += 1
            self.__evaluate_check(check_list, counter, finished_deferred)
            return result

        def __evaluate_errback(result, params):
            """Called when an error occurred in processing a test condition"""
            check_list, counter, finished_deferred = params
            LOGGER.warning("Failed to evaluate condition check %s" %
                           str(result))
            self.__check_observers(result)
            counter += 1
            self.__evaluate_check(check_list, counter, finished_deferred)
            return result

        if (counter >= len(check_list)):
            # All done - raise the finished deferred
            finished_deferred.callback(self)
            return

        # A check object is a tuple of a pre/post condition check, and either
        # a matching check object used in the evaluation, or None
        condition, related_condition = check_list[counter]

        # Check to see if the build supports this condition check
        if not (condition.check_build_options()):
            counter += 1
            self.__evaluate_check(check_list, counter, finished_deferred)

        for ast in self._ast:
            condition.register_asterisk_instance(ast)
        if (condition.get_enabled()):
            LOGGER.debug("Evaluating %s" % condition.get_name())
            defrd = condition.evaluate(related_test_condition=related_condition)
            params = check_list, counter, finished_deferred
            defrd.addCallback(__evaluate_callback, params=params)
            defrd.addErrback(__evaluate_errback, params=params)

    def __check_observers(self, test_condition):
        """Notify observers that a test condition finished"""

        for observer_tuple in self._observers:
            observer, cond_filter = observer_tuple
            if (cond_filter == "" or
                    (cond_filter == test_condition.get_status())):
                observer(test_condition)

        if (test_condition.get_status() == 'Failed' and
                self._stop_test_callback is not None):
            self._stop_test_callback()


TEST_STATUSES = enum(Inconclusive='Inconclusive',
                     Failed='Failed',
                     Passed='Passed')


class TestCondition(object):
    """The test condition base class.

    This object provides the evaluate method signature which must be overriden,
    and various helper methods to print out and save the status of the test
    condition check
    """

    build_options = AsteriskBuildOptions()

    def __init__(self, test_config):
        """Initialize a new test condition

        Keyword arguments:
        test_config The test configuration object that defines this
                    Test Condition
        """
        self.failure_reasons = []
        self._name = test_config.class_type_name
        self._test_status = TEST_STATUSES.Inconclusive
        self.ast = []
        self.my_build_options = []
        self._enabled = test_config.enabled
        self.pass_expected = test_config.pass_expected

    def __str__(self):
        """Convert the object to a string representation"""
        status = "Test Condition [%s]: [%s]" % (self._name, self._test_status)
        if (self._test_status == TEST_STATUSES.Failed):
            for reason in self.failure_reasons:
                status += "\n\tReason: %s" % reason
        return status

    def check_build_options(self):
        """Checks the required Asterisk Build Options for this TestCondition.

        Returns:
        True if all conditions are met
        False if a condition was not met.
        """
        ret_val = True
        for option in self.my_build_options:
            build_option, expected_value = option
            if not TestCondition.build_options.check_option(build_option,
                                                            expected_value):
                LOGGER.debug("Build option %s not set to %s; test condition "
                             "[%s] will not be checked" % (build_option,
                                                           expected_value,
                                                           self._name))
                ret_val = False
        return ret_val

    def add_build_option(self, option_name, expected_value="1"):
        """Add a build option in Asterisk to check for before executing this
        condition.

        Keyword arguments:
        option_name    The name of the Asterisk build option to check for
        expected_value The value the build option must have in order for this
                       condition to execute
        """
        self.my_build_options.append((option_name, expected_value))

    def register_asterisk_instance(self, ast):
        """Register an instance of asterisk to be tested by this condition.

        Note that you are guaranteed to have all instances of Asterisk that
        should be checked by the condition by the time the evaluate method is
        called.

        Keyword arguments:
        ast An instance of Asterisk to check
        """
        self.ast.append(ast)

    def evaluate(self, related_test_condition=None):
        """Evaluate the test condition

        Derived classes must implement this method and check their test
        condition here. If the test condition passes they should call
        pass_check, otherwise they should call fail_check.  Each test condition
        must return a twisted deferred, and raise a callback on the deferred
        when the condition is finished being evaluated.

        They may raise an errback if a serious error occurs in the evaluation.

        In either case, the should pass themselves to the callback/errback.

        Keyword arguments:
        related_test_condition  A test condition object that is related to this
                                one. Provided if specified when this test
                                condition is registered to the test condition
                                controller.
        Returns:
        A twisted deferred object
        """
        pass

    def get_enabled(self):
        """True if the condition is enabled and should run, false otherwise"""
        return self._enabled

    def get_name(self):
        """The name of the test condition"""
        return self._name

    def get_status(self):
        """The current status of the test"""
        return str(self._test_status)

    def pass_check(self):
        """Mark that the test condition has passed.

        Note that this will not overwrite a previous indication that the test
        condition failed.
        """
        if (self._test_status == TEST_STATUSES.Inconclusive):
            self._test_status = TEST_STATUSES.Passed

    def fail_check(self, reason=""):
        """Mark that the test condition has failed.

        Note that the test condition cannot be changed once placed in this
        state.

        Keyword arguments:
        reason The reason the test failed
        """
        self._test_status = TEST_STATUSES.Failed
        if (reason != ""):
            self.failure_reasons.append(reason)
