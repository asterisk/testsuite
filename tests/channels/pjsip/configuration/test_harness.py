#!/usr/bin/env python
"""
Copyright (C) 2015, Digium, Inc.
Ashley Sanders <asanders@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging

sys.path.append("lib/python")
sys.path.append("tests/channels/pjsip/configuration")

from test_scenario import TestScenario

LOGGER = logging.getLogger(__name__)


class TestHarness(object):
    """The test harness.

    This class creates and manages the life-cycle of the the objects needed to
    execute the test plan.
    """

    def __init__(self, config, test_object):
        """Constructor.

        Keyword Arguments:
        config                 -- The YAML configuration for this test.
        test_object            -- The TestCaseModule instance for this test.
        """

        self.__messages = self.__initialize_messages()
        LOGGER.debug(self.__messages['initializing_harness'])

        self.test_object = test_object

        self.__scenarios = self.__build_scenarios(self.__load_config(config))

        self.test_object.register_stop_observer(self.__on_asterisk_stop)
        self.test_object.register_ami_observer(self.__on_ami_connect)

        return

    def __format__(self, format_spec):
        """Overrides default format handling for 'self'."""

        return self.__class__.__name__ + ':'

    def __build_scenarios(self, config_scenarios):
        """Builds the scenarios.

        Keyword Arguments:
        config_scenarios       -- The test-scenarios section from the YAML
                                  configuration.

        Returns:
        A list of scenarios.
        """

        LOGGER.debug(self.__messages['building_scenarios'])
        scenarios = list()
        LOGGER.info('config_scenarios=%r' % config_scenarios)

        for i in range(0, self.test_object.asterisk_instances):
            config_scenario = config_scenarios[i]
            scenario = TestScenario(config_scenario['cli_command'],
                                    config_scenario['output_query'],
                                    self.__on_scenario_complete)
            scenarios.append(scenario)
        return scenarios

    def __initialize_messages(self):
        """Creates a dictionary of pre-formatted logger messages.

        Returns:
        A dictionary of pre-formatted logger messages.
        """

        messages = dict()

        base_msg = '{0} '.format(self)
        messages['aborting_config_error'] = base_msg + \
            'Aborting test. Configuration contains errors.'
        messages['calculating_results'] = base_msg + \
            'Calculating test results.'
        messages['building_scenarios'] = base_msg + \
            'Building test scenarios.'
        messages['initializing_harness'] = base_msg + \
            'Initializing test harness.'
        messages['loading_config'] = base_msg + \
            'Loading module configuration.'
        messages['missing_attribute'] = base_msg + \
            '{0} is missing required attribute \'{1}\'.'
        messages['missing_config'] = base_msg + \
            'No configuration provided.'
        messages['querying_scenarios'] = base_msg + \
            'Querying test scenarios.'
        messages['starting_scenario'] = base_msg + \
            'Starting execution for scenario[{0}]'
        messages['test_complete'] = base_msg + \
            'Test case execution is complete.'
        messages['unsupported_attribute'] = base_msg + \
            'Unsupported configuration attribute \'{0}\' specified.'
        messages['validating_config'] = base_msg + \
            'Validating module configuration.'

        return messages

    def __load_config(self, config):
        """Loads the module configuration.

        Keyword Arguments:
        config                 -- The YAML configuration for this test.

        Returns a list of cli_command/output_query objects to use as test
        conditions for running the scenario.
        """

        if not self.__validate_config(config):
            LOGGER.error(self.__messages['aborting_config_error'])
            self.test_object.stop_reactor()

        LOGGER.debug(self.__messages['loading_config'])

        return config['test-scenarios']

    def __on_ami_connect(self, ami):
        """Handler for the AMI connect event.

        Keyword Arguments:
        ami                    -- The AMI instance that raised this event.
        """

        index = ami.id
        LOGGER.info(self.__messages['starting_scenario'].format(index))
        scenario = self.__scenarios[index]
        scenario.run(self.test_object.ast[index])
        return

    def __on_asterisk_stop(self, result):
        """Determines the overall pass/fail state for the test prior to
        shutting down the reactor.

        Keyword Arguments:
        result                 -- A twisted deferred object

        Returns:
        A twisted deferred object.
        """

        LOGGER.debug(self.__messages['calculating_results'])
        for scenario in self.__scenarios:
            self.test_object.set_passed(scenario.passed)
        return result

    def __on_scenario_complete(self, message):
        """Queries the scenarios to determine if the test is complete.

        Keyword Arguments:
        message                -- The event payload.
        """

        LOGGER.debug(self.__messages['querying_scenarios'])

        for scenario in self.__scenarios:
            if not scenario.finished:
                return

        LOGGER.debug(self.__messages['test_complete'])
        self.test_object.stop_reactor()

    def __validate_config(self, config):
        """Validates the module configuration for this test.

        Keyword Arguments:
        config                 -- The YAML configuration for this test.

        Returns:
        True if the configuration is valid, False otherwise.
        """

        LOGGER.debug(self.__messages['validating_config'])

        if not config:
            LOGGER.error(self.__messages['missing_config'])
            return False

        if 'test-scenarios' not in config:
            msg = self.__messages['missing_attribute']
            LOGGER.error(msg.format('Configuration', 'test-scenarios'))
            return False

        valid = None

        for scenario in config['test-scenarios']:
            if 'cli_command' not in scenario:
                msg = self.__messages['missing_attribute']
                LOGGER.error(msg.format('\'test-scenario\' attribute',
                                        'cli_command'))
                valid = False

            if 'output_query' not in scenario:
                msg = self.__messages['missing_attribute']
                LOGGER.error(msg.format('\'test-scenario\' attribute',
                                        'output_query'))
                valid = False

            for key in scenario.keys():
                k = key.lower()
                if k != 'cli_command' and k != 'output_query':
                    msg = self.__messages['unsupported_attribute'].format(key)
                    LOGGER.error(msg)
                    valid = False

        return valid if valid is not None else True
