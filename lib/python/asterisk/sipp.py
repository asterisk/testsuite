""" SIPp based tests.

This module provides a class that implements a test of a single Asterisk
instance using 1 or more SIPp scenarios.

Copyright (C) 2010, Digium, Inc.
Russell Bryant <russell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import os
import subprocess
import logging
import TestSuiteUtils

from twisted.internet import reactor, defer, utils, protocol
from asterisk import Asterisk
from TestCase import TestCase

LOGGER = logging.getLogger(__name__)

class SIPpTestCase(TestCase):
    ''' A SIPp test object for the pluggable framework.

    In addition to the 'normal' entry points that TestCase defines for
    modules to attach themselves, this Test Object defines the following:

    register_scenario_started_observer - add a callback function that will be
        called every time a SIPp Scenario starts

    register_scenario_stopped_observer - add a callback function that will be
        called every time a SIPp Scenario stops

    register_intermediate_observer - add a callback function that will be called
        between sets of SIPp Scenarios run in parallel

    register_final_observer - add a callback function that will be called when
        all SIPp Scenarios have finished, but before the reactor is stopped
    '''

    def __init__(self, test_path, test_config):
        ''' Constructor

        Parameters:
        test_path path to the location of the test directory
        test_config yaml loaded object containing config information
        '''
        super(SIPpTestCase, self).__init__(test_path)

        if not test_config:
            raise ValueError('SIPpTestObject requires a test config')

        self._scenario_started_observers = []
        self._scenario_stopped_observers = []
        self._intermediate_observers = []
        self._final_observers = []
        self._test_config = test_config
        self._current_test = 0
        if 'fail-on-any' in self._test_config:
            self._fail_on_any = self._test_config['fail-on-any']
        else:
            self._fail_on_any = True

        self.register_intermediate_obverver(self._handle_scenario_finished)
        self.create_asterisk()


    def run(self):
        ''' Override of the run method.  Create an AMI factory in case anyone
        wants it '''
        super(SIPpTestCase, self).run()
        self.create_ami_factory()

        self.ast[0].cli_exec('sip set debug on')


    def ami_connect(self, ami):
        ''' Handler for the AMI connect event '''
        super(SIPpTestCase, self).ami_connect(ami)

        self._execute_test()


    def register_scenario_started_observer(self, observer):
        ''' Register a function to be called when a SIPp scenario starts.

        Keywords:
        observer The function to be called.  The function should take in a
            single parameter, the SIPpScenario object that started.
        '''
        self._scenario_started_observers.append(observer)


    def register_scenario_stopped_observer(self, observer):
        ''' Register a function to be called when a SIPp scenario stops.

        Keywords:
        observer The function to be called.  The function should take in a
        single parameter, the SIPpScenario object that stopped.
        '''
        self._scenario_stopped_observers.append(observer)


    def register_intermediate_obverver(self, observer):
        ''' Register a function to be called in between SIPp scenarios.

        Keywords:
        observer The function to be called.  The function should take in a
            single parameter, a list of tuples.  Each tuple will be
            (success, result), where success is the pass/fail status of the
            SIPpScenario, and result is the SIPpScenario object.
        '''

        self._intermediate_observers.append(observer)


    def register_final_observer(self, observer):
        ''' Register a final observer, called when all SIPp scenarios are done
        in a given sequence

        Keywords:
        observer The function to be called.  The function should take in two
            parameters: an integer value indicating which test iteration is
            being executed, and this object.
        '''

        self._final_observers.append(observer)


    def _handle_scenario_finished(self, result):
        ''' Handle whether or not a scenario finished successfully '''
        for (success, scenario) in result:
            if (success):
                LOGGER.info("Scenario %s passed" %
                            (scenario.name))
                self.set_passed(True)
            else:
                # Note: the SIPpSequence/Scenario objects will auto fail this test
                # if configured to do so.  Merely report pass/fail here.
                LOGGER.warning("Scenario %s failed" %
                               (scenario.name))
                self.set_passed(False)


    def _execute_test(self):
        def _final_deferred_callback(result):
            for observer in self._final_observers:
                observer(self._current_test, self)
            return result

        def _finish_test(result):
            LOGGER.info("All SIPp Scenarios executed; stopping reactor")
            self.stop_reactor()
            return result

        scenarios = []
        for defined_scenario_set in self._test_config['test-iterations']:

            scenario_set = defined_scenario_set['scenarios']
            # Build a list of SIPpScenario objects to run in parallel from
            # each set of scenarios in the YAML config
            scenarios.append([SIPpScenario(self.test_name,
                                           scenario['key-args'],
                                           [] if 'ordered-args' not in scenario else scenario['ordered-args'])
                                           for scenario in scenario_set])

        final_deferred = defer.Deferred()
        final_deferred.addCallback(_final_deferred_callback)
        final_deferred.addCallback(_finish_test)
        sipp_sequence = SIPpScenarioSequence(self,
                                             scenarios,
                                             self._fail_on_any,
                                             self._intermediate_callback_fn,
                                             final_deferred)
        sipp_sequence.register_scenario_start_callback(self._scenario_start_callback_fn)
        sipp_sequence.register_scenario_stop_callback(self._scenario_stop_callback_fn)
        sipp_sequence.execute()


    def _intermediate_callback_fn(self, result):
        for observer in self._intermediate_observers:
            observer(result)
        return result


    def _scenario_start_callback_fn(self, result):
        for observer in self._scenario_started_observers:
            observer(result)
        return result


    def _scenario_stop_callback_fn(self, result):
        for observer in self._scenario_stopped_observers:
            observer(result)
        return result


class SIPpScenarioSequence:
    ''' Execute a sequence of SIPp Scenarios in sequence.

    This class manages the execution of multiple SIPpScenarios in sequence.
    '''

    def __init__(self, test_case, sipp_scenarios = [],
                 fail_on_any = False,
                 intermediate_cb_fn = None,
                 final_deferred = None):
        ''' Create a new sequence of scenarios

        Keyword Arguments:
        test_case - the TestCase derived object to pass to the SIPpScenario objects
        sipp_scenarios - a list of SIPpScenario objects to execute, or a list of
            lists of SIPpScenario objects to execute in parallel
        fail_on_any - if any scenario fails, stop the reactor and kill the test.
        intermediate_cb_fn - a callback function suitable as a DeferredList callback
            that will be added to each SIPpScenario.  What is received will be
            a list of (success, result) tuples for each scenario that was
            executed, where the result object is the SIPpScenario.  This will be
            called for each set of SIPpScenario objects.
        final_deferred - a deferred object that will be called when all tests have
            executed, but before the reactor is stopped.  The parameter passed
            to the deferred callback function will be this object.
        '''
        self.__sipp_scenarios = sipp_scenarios
        self.__test_case = test_case
        self.__fail_on_any = fail_on_any
        self.__test_counter = 0
        self.__intermediate_cb_fn = intermediate_cb_fn
        self.__final_deferred = final_deferred
        self.__scenario_start_fn = None
        self.__scenario_stop_fn = None


    def register_scenario_start_callback(self, callback_fn):
        ''' Register a callback function that will be called on the start of
        every SIPpScenario

        Keyword Arguments:
        callback_fn A function that takes in a single parameter.  That parameter
        will be the SIPpScenario object that was just started
        '''
        self.__scenario_start_fn = callback_fn


    def register_scenario_stop_callback(self, callback_fn):
        ''' Register a callback function that will be called at the end of
        every SIPpScenario

        Keyword Arguments:
        callback_fn A function that acts as a deferred callback.  It takes in
        a single parameter that will be the SIPpScenario object.
        '''
        self.__scenario_stop_fn = callback_fn


    def register_scenario(self, sipp_scenario):
        ''' Register a new scenario with the sequence

        Registers a SIPpScenario object with the sequence of scenarios to execute

        Keyword Arguments:
        sipp_scenario - the SIPpScenario object to execute
        '''
        self.__sipp_scenarios.append(sipp_scenario)

    def execute(self):
        ''' Execute the tests in sequence
        '''
        def __execute_next(result):
            ''' Execute the next SIPp scenario in the sequence '''
            # Only evaluate for failure if we're responsible for failing the test case -
            # otherwise the SIPpScenario will do it for us
            for (success, scenario) in result:
                if not self.__fail_on_any and (not scenario.passed or not success):
                    LOGGER.warning("SIPp Scenario %s Failed" % scenario.name)
                    self.__test_case.set_passed(False)
            self.__test_counter += 1
            if self.__test_counter < len(self.__sipp_scenarios):
                self.execute()
            else:
                if self.__final_deferred:
                    self.__final_deferred.callback(self)
                self.__test_case.stop_reactor()
            return result

        scenarios = self.__sipp_scenarios[self.__test_counter]
        # Turn the scenario into a list if all we got was a single scenario to
        # execute
        if type(scenarios) is not list:
            scenarios = [scenarios]

        deferds = []
        for scenario in scenarios:
            # If we fail on any, let the SIPp scenario handle it by passing it
            # the TestCase object
            if self.__fail_on_any:
                df = scenario.run(self.__test_case)
            else:
                df = scenario.run(None)
            # Order here is slightly important.  Add all the callbacks to the
            # scenario's deferred object first, then add it to the list.
            # Afterwards, notify start observers that we're started.
            if self.__scenario_stop_fn:
                df.addCallback(self.__scenario_stop_fn)
            if self.__scenario_start_fn:
                self.__scenario_start_fn(scenario)
            deferds.append(df)

        dl = defer.DeferredList(deferds)
        if self.__intermediate_cb_fn:
            dl.addCallback(self.__intermediate_cb_fn)
        dl.addCallback(__execute_next)


class SIPpScenario:
    """
    A SIPp based scenario for the Asterisk testsuite.

    Unlike SIPpTest, SIPpScenario does not attempt to manage the Asterisk instance.
    Instead, it will launch a SIPp scenario, assuming that there is an instance of
    Asterisk already in existence to handle the SIP messages.  This is useful
    when a SIPp scenario must be integrated with a more complex test (using the TestCase
    class, for example)
    """
    def __init__(self, test_dir, scenario, positional_args=()):
        """
        Arguments:

        test_dir - The path to the directory containing the run-test file.

        scenario - a SIPp scenario to execute.  The scenario should
        be a dictionary with the key 'scenario' being the filename
        of the SIPp scenario.  Any other key-value pairs are treated as arguments
        to SIPp.  For example, specify '-timeout' : '60s' to set the
        timeout option to SIPp to 60 seconds.  If a parameter specified
        is also one specified by default, the value provided will be used.
        The default SIPp parameters include:
            -p <port>    - Unless otherwise specified, the port number will
                           be 5060 + <scenario list index, starting at 1>.
                           So, the first SIPp sceario will use port 5061.
            -m 1         - Stop the test after 1 'call' is processed.
            -i 127.0.0.1 - Use this as the local IP address for the Contact
                           headers, Via headers, etc.
            -timeout 20s - Set a global test timeout of 20 seconds.

        positional_args - certain SIPp parameters can be specified multiple
        times, or take multiple arguments. Supply those through this iterable.
        The canonical example being -key:
            ('-key', 'extra_via_param', ';rport',
             '-key', 'user_addr', 'sip:myname@myhost')
        """
        self.scenario = scenario
        self.name = scenario['scenario']
        self.positional_args = tuple(positional_args) # don't allow caller to mangle his own list
        self.test_dir = test_dir
        self.default_port = 5061
        self.sipp = TestSuiteUtils.which("sipp")
        self.passed = False

    def run(self, test_case = None):
        """ Execute a SIPp scenario

        Execute the SIPp scenario that was passed to this object

        Keyword Arguments:
        test_case - if not None, the scenario will automatically evaluate its pass/fail status
        at the end of the run.  In the event of a failure, it will fail the test case scenario
        and call stop_reactor.

        Returns:
        A deferred that can be used to determine when the SIPp Scenario
        has exited.
        """

        def __output_callback(result):
            """ Callback from getProcessOutputAndValue """
            out, err, code = result
            LOGGER.debug("Launching SIPp Scenario %s exited %d"
                % (self.scenario['scenario'], code))
            if (code == 0):
                self.passed = True
                LOGGER.info("SIPp Scenario %s Exited" % (self.scenario['scenario']))
            else:
                LOGGER.warning("SIPp Scenario %s Failed [%d, %s]" % (self.scenario['scenario'], code, err))
            self.__exit_deferred.callback(self)

        def __error_callback(result):
            """ Errback from getProcessOutputAndValue """
            out, err, code = result
            LOGGER.warning("SIPp Scenario %s Failed [%d, %s]" % (self.scenario['scenario'], code, err))
            self.__exit_deferred.callback(self)

        def __evalute_scenario_results(result):
            """ Convenience function.  If the test case is injected into this method,
            then auto-fail the test if the scenario fails. """
            if not self.passed:
                LOGGER.warning("SIPp Scenario %s Failed" % self.scenario['scenario'])
                self.__test_case.passed = False
                self.__test_case.stop_reactor()

        sipp_args = [
                self.sipp, '127.0.0.1',
                '-sf', '%s/sipp/%s' % (self.test_dir, self.scenario['scenario']),
                '-nostdin',
                '-skip_rlimit',
        ]
        default_args = {
            '-p' : str(self.default_port),
            '-m' : '1',
            '-i' : '127.0.0.1',
            '-timeout' : '20s'
        }

        # Override and extend defaults
        default_args.update(self.scenario)
        del default_args['scenario']

        for (key, val) in default_args.items():
            sipp_args.extend([ key, val ])
        sipp_args.extend(self.positional_args)

        LOGGER.info("Executing SIPp scenario: %s" % self.scenario['scenario'])
        LOGGER.debug(sipp_args)

        self.__exit_deferred = defer.Deferred()

        df = utils.getProcessOutputAndValue(sipp_args[0], sipp_args, {"TERM" : "vt100",}, None, None)
        df.addCallbacks(__output_callback, __error_callback)
        if test_case:
            self.__test_case = test_case
            df.addCallback(__evalute_scenario_results)

        return self.__exit_deferred

class SIPpTest(TestCase):
    """
    A SIPp based test for the Asterisk testsuite.

    This is a common implementation of a test that uses 1 or more SIPp
    scenarios.  The result code of each SIPp instance is used to determine
    whether or not the test passed.

    This class currently uses a single Asterisk instance and runs all of the
    scenarios against it.  If any configuration needs to be provided to this
    Asterisk instance, it is expected to be in the configs/ast1/ direcotry
    under the test_dir provided to the constructor.  This directory was
    chosen based on the convention that has been established in the testsuite
    for the location of configuration for a test.
    """

    def __init__(self, working_dir, test_dir, scenarios):
        """

        Arguments:

        working_dir - Deprecated.  No longer used.

        test_dir - The path to the directory containing the run-test file.

        scenarios - A list of SIPp scenarios.  This class expects these
            to exist in the sipp directory under test_dir.  The list must be
            constructed as a list of dictionaries.  Each dictionary must have
            the key 'scenario' with the value being the filename of the SIPp
            scenario.  Any other key-value pairs are treated as arguments
            to SIPp.  For example, specity '-timeout' : '60s' to set the
            timeout option to SIPp to 60 seconds.  If a parameter specified
            is also one specified by default, the value provided will be used.
            The default SIPp parameters include:
                -p <port>    - Unless otherwise specified, the port number will
                               be 5060 + <scenario list index, starting at 1>.
                               So, the first SIPp sceario will use port 5061.
                -m 1         - Stop the test after 1 'call' is processed.
                -i 127.0.0.1 - Use this as the local IP address for the Contact
                               headers, Via headers, etc.
                -timeout 20s - Set a global test timeout of 20 seconds.
        """
        TestCase.__init__(self)
        self.test_dir = test_dir
        self.scenarios = scenarios
        self.result = []
        self.create_asterisk()

    def run(self):
        """
        Run the test.

        Returns 0 for success, 1 for failure.
        """
        def __check_result(result):
            """ Append the result of the test to our list of results """
            self.result.append(result.passed)
            return result

        def __set_pass_fail(result):
            """ Check if all tests have passed - if any have failed, set our passed status to False """
            self.passed = (self.result.count(False) == 0)
            self.stop_reactor()
            return result

        TestCase.run(self)

        i = 0
        deferds = []
        for s in self.scenarios:
            default_port = 5060 + i + 1
            i += 1
            if not '-p' in s:
                s['-p'] = str(default_port)
            scenario = SIPpScenario(self.test_dir, s)
            df = scenario.run(self)
            df.addCallback(__check_result)
            deferds.append(df)

        fin = defer.DeferredList(deferds)
        fin.addCallback(__set_pass_fail)

