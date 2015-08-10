'''
Copyright (C) 2015, Digium, Inc.
Ashley Sanders <asanders@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging

sys.path.append("lib/python")
sys.path.append("tests/channels/SIP/tcpauthlimit")

from sip_client_scenario import SipClientScenario
from sipp_scenario_wrapper import SIPpScenarioWrapper
from twisted.internet import defer

LOGGER = logging.getLogger(__name__)


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

        self.__test_object.register_stop_observer(self.__on_asterisk_stop)
        self.__test_object.register_ami_observer(self.__on_ami_connected)

        self.__remote_host = config['remote-host'][0]
        self.__tcpauthlimit = config['tcpauthlimit']

        self.__scenarios = self.__build_scenarios(config['test-scenarios'])

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
            skip = config_scenario.get('skip') or None

            if scenario_type.lower() == 'sip-client':
                scenario = SipClientScenario(scenario_id,
                                             skip,
                                             remote_address,
                                             remote_port,
                                             tcpauthlimit)
            elif scenario_type.lower() == 'sipp-scenario':
                key_args = config_scenario['key-args']
                ordered_args = config_scenario.get('ordered-args') or []
                target = config_scenario.get('target') or remote_address
                scenario = SIPpScenarioWrapper(self.__test_object.test_name,
                                               key_args,
                                               ordered_args,
                                               target,
                                               scenario_id,
                                               skip)
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

    def __evaluate_test_results(self):
        """Evaluates the test results.

        First, the method analyzes the SIPpScenarioWrapper instances to
        determine if the number of those scenarios that passed equals the
        tcpauthlimit (maximum number of connections permitted). Because more
        scenarios are executed than the number of connections permitted, some
        of these scenarios are expected to fail.

        Finally, the remaining SIP client scenarios are queried for their
        default pass/fail status.

        Returns True on success, False otherwise.
        """

        def __get_scenarios(scenario_type):
            """Creates a scenario generator for the given scenario type.

            Keyword Arguments:
            scenario_type      -- The type of scenario instance for the
                                  generator to return.
            """

            for scenario in self.__scenarios:
                if not scenario.suspended:
                    if scenario.__class__.__name__ == scenario_type:
                        yield scenario

        LOGGER.debug('{0} Evaluating test results...'.format(self))

        msg = '{0} Evaluating SIPp scenario results...'.format(self)
        LOGGER.debug(msg)

        scenario_count = sum(1 for s in __get_scenarios('SIPpScenarioWrapper'))
        if scenario_count == 0:
            msg = '{0} No SIPp scenario results to evaluate.'
            LOGGER.debug(msg.format(self))
        else:
            actual = 0
            expected = (
                scenario_count if scenario_count < self.__tcpauthlimit
                else self.__tcpauthlimit)
            scenarios = __get_scenarios('SIPpScenarioWrapper')

            for scenario in scenarios:
                if scenario.passed:
                    actual += 1

                if actual <= expected:
                    scenario.adjust_result()
                else:
                    scenario.adjust_result(255)

            if actual != expected:
                msg = '{0} One or more SIPp scenarios failed.'.format(self)
                LOGGER.error(msg)
                return False

            msg = '{0} All SIPp scenarios passed.'.format(self)
            LOGGER.debug(msg)

        msg = '{0} Evaluating SIP client scenario results...'.format(self)
        LOGGER.debug(msg)

        if sum(1 for s in __get_scenarios('SipClientScenario')) == 0:
            msg = '{0} No SIP client scenario results to evaluate.'
            LOGGER.debug(msg.format(self))
            return True

        if all(s.passed for s in __get_scenarios('SipClientScenario')):
            msg = '{0} All SIP client scenarios passed.'.format(self)
            LOGGER.debug(msg)
            return True

        msg = '{0} One or more SIP client scenarios failed.'.format(self)
        LOGGER.error(msg)
        return False

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
            if scenario.suspended:
                msg = 'skipped \'scenario %s\': %s'
                console_msg = '--> %s ... ' % self.__test_object.test_name + msg
                logger_msg = '{0} '.format(self) + msg.capitalize()
                print console_msg % (scenario.scenario_id, scenario.status)
                LOGGER.info(logger_msg.format(scenario.scenario_id,
                                              scenario.status))
            else:
                deferred = scenario.run()
                deferreds.append(deferred)

        defer.DeferredList(deferreds).addCallback(__tear_down_test)
