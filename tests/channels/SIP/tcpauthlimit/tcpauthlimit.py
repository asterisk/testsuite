#!/usr/bin/env python
'''
Copyright (C) 2015, Digium, Inc.
Ashley Sanders <asanders@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging

sys.path.append("lib/python/asterisk")

from sipp_scenario import SIPpScenarioWrapper
from twisted.internet import defer

LOGGER = logging.getLogger(__name__)


def get_friendly_scenario_type(scenario_type):
    """Returns the logger friendly name for the given scenario type.

    Keyword Arguments:
    scenario_type              -- The type of scenario.
    """

    if scenario_type == 'SIPpScenarioWrapper':
        return 'SIPp scenario'

    return 'Unknown type scenario'


class TcpAuthLimitTestModule(object):
    """The test module.

    This class serves as a harness for the test scenarios. It manages the
    life-cycle of the the objects needed to execute the test plan.
    """

    def __init__(self, config, test_object):
        """Constructor.

        Keyword Arguments:
        config                 -- The YAML configuration for this test.
        test_object            -- The TestCaseModule instance for this test.
        """

        self.__test_object = test_object
        self.__remote_host = config['remote-host'][0]
        self.__tcpauthlimit = config['tcpauthlimit']
        self.__scenarios = self.__build_scenarios(config['test-scenarios'])

        self.__test_object.register_stop_observer(self.__on_asterisk_stop)
        self.__test_object.register_ami_observer(self.__on_ami_connected)

    def __build_scenarios(self, config_scenarios):
        """Builds the scenarios.

        Keyword Arguments:
        config_scenarios       -- The test-scenarios section from the YAML
                                  configuration.

        Returns:
        A list of scenarios on success. None on error.
        """

        scenarios = list()

        msg = '{0} Building test scenarios.'
        LOGGER.debug(msg.format(self))

        remote_address = self.__remote_host['address']
        remote_port = self.__remote_host['port']
        tcpauthlimit = self.__tcpauthlimit

        for config_scenario in config_scenarios:
            scenario_type = config_scenario['type']
            scenario_id = config_scenario.get('scenario-id') or None

            if scenario_type.lower() == 'sipp-scenario':
                key_args = config_scenario['key-args']
                ordered_args = config_scenario.get('ordered-args') or []
                target = config_scenario.get('target') or remote_address
                scenario = SIPpScenarioWrapper(self.__test_object.test_name,
                                               key_args,
                                               ordered_args,
                                               target,
                                               scenario_id)
            else:
                msg = '{0} [{1}] is not a recognized scenario type.'
                LOGGER.error(msg.format(self, scenario_type))
                return None
            scenarios.append(scenario)

        if len(scenarios) == 0:
            msg = '{0} Failing the test. No scenarios registered.'
            LOGGER.error(msg.format(self))
            self.__test_object.set_passed(False)
            self.__test_object.stop_reactor()

        return scenarios

    def __evaluate_scenario_results(self, scenario_type):
        """Evaluates the results for the given scenario type.

        For SIPpScenarioWrapper scenario type evaluations, the scenarios are
        polled to determine if the number of those scenarios that passed equals
        the tcpauthlimit (maximum number of connections permitted). Because
        more scenarios are executed than the number of connections permitted,
        some of these scenarios are expected to fail.

        Keyword Arguments:
        scenario_type          -- The type of scenario instances to analyze.

        Returns True on success, False otherwise.
        """

        def __get_scenarios(scenario_type):
            """Creates a scenario generator for the given scenario type.

            Keyword Arguments:
            scenario_type      -- The type of scenario instance for the
                                  generator to return.

            Returns a generator for the scenarios found matching the given
            scenario type.
            """

            for scenario in self.__scenarios:
                if scenario.__class__.__name__ == scenario_type:
                    yield scenario

        friendly_type = get_friendly_scenario_type(scenario_type)
        scenario_count = sum(1 for s in __get_scenarios(scenario_type))

        msg = '{0} Evaluating {1} results...'.format(self, friendly_type)
        LOGGER.debug(msg)

        if scenario_count == 0:
            msg = '{0} No {1} results to evaluate.'
            LOGGER.debug(msg.format(self, friendly_type))
            return True
        else:
            actual = 0
            msg = '{0} {1} \'{2}\' {3}.'

            if scenario_type == 'SIPpScenarioWrapper':
                expected = (
                    scenario_count if scenario_count < self.__tcpauthlimit
                    else self.__tcpauthlimit)
            else:
                expected = 1

            for scenario in __get_scenarios(scenario_type):
                if scenario.passed:
                    actual += 1

                if scenario_type == 'SIPpScenarioWrapper':
                    if actual <= expected:
                        scenario.adjust_result()
                    else:
                        scenario.adjust_result(255)

                if scenario.passed:
                    LOGGER.debug(msg.format(self,
                                            friendly_type,
                                            scenario.scenario_id,
                                            'passed'))
                else:
                    LOGGER.debug(msg.format(self,
                                            friendly_type,
                                            scenario.scenario_id,
                                            'failed'))

            if actual != expected:
                msg = '{0} One or more {1}s failed.'
                LOGGER.error(msg.format(self, friendly_type))
                return False

            msg = '{0} All {1}s passed.'
            LOGGER.debug(msg.format(self, friendly_type))
            return True

    def __evaluate_test_results(self):
        """Evaluates the test results.

        First, the method analyzes the SIPpScenarioWrapper instances (if any)
        then analyzes the remaining TCP client scenarios (if any).

        Returns True on success, False otherwise.
        """

        LOGGER.debug('{0} Evaluating test results...'.format(self))

        return self.__evaluate_scenario_results('SIPpScenarioWrapper')

    def __format__(self, format_spec):
        """Overrides default format handling for 'self'."""

        return self.__class__.__name__ + ':'

    def __on_ami_connected(self, ami):
        """Handler for the AMI connect event.

        Keyword Arguments:
        ami                    -- The AMI instance that raised this event.
        """

        self.__run_scenarios()

    def __on_asterisk_stop(self, result):
        """Determines the overall pass/fail state for the test prior to
        shutting down the reactor.

        Keyword Arguments:
        result                 -- A twisted deferred instance.

        Returns:
        A twisted deferred instance.
        """

        self.__test_object.set_passed(self.__evaluate_test_results())
        msg = '{0} Test {1}.'
        if self.__test_object.passed:
            LOGGER.info(msg.format(self, 'passed'))
        else:
            LOGGER.error(msg.format(self, 'failed'))
        return result

    def __run_scenarios(self):
        """Executes the scenarios."""

        def __tear_down_test(message):
            """Tears down the test.

            Keyword Arguments:
            message            -- The event payload.
            """

            LOGGER.debug('{0} Stopping reactor.'.format(self))
            self.__test_object.stop_reactor()
            return message

        LOGGER.debug('{0} Running test scenarios.'.format(self))

        deferreds = []
        for scenario in self.__scenarios:
            deferred = scenario.run()
            deferreds.append(deferred)

        defer.DeferredList(deferreds).addCallback(__tear_down_test)
