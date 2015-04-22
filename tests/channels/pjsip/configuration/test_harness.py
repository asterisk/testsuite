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

        LOGGER.debug('{0} Initializing test harness.'.format(self))

        self.test_object = test_object
        self.scenarios = self.__build_scenarios(config)

        self.test_object.register_stop_observer(self.__on_asterisk_stop)
        self.test_object.register_ami_observer(self.__on_ami_connect)


    def __format__(self, format_spec):
        """Overrides default format handling for 'self'."""

        return self.__class__.__name__ + ':'

    def __build_scenarios(self, config):
        """Builds the scenarios.

        Keyword Arguments:
        config                 -- The YAML configuration for this test.

        Returns:
        A list of scenarios.
        """

        LOGGER.debug('{0} Building test scenarios.'.format(self))

        if not self.__validate_config(config):
            LOGGER.error('{0} Aborting test. Configuration contains errors.')
            self.test_object.stop_reactor()

        scenarios = list()
        for _ in range(0, self.test_object.asterisk_instances):
            scenario = TestScenario(config['cli_command'],
                                    config['re_query'])
            scenarios.append(scenario)
        return scenarios

    def __on_ami_connect(self, ami):
        """Handler for the AMI connect event.

        Keyword Arguments:
        ami                    -- The AMI instance that raised this event.
        """

        index = ami.id
        LOGGER.info('{0} Starting execution for scenario[{1}].'.format(self,
                                                                       index))
        scenario = self.scenarios[index]
        deferred = scenario.run(self.test_object.ast[index])
        deferred.addCallbacks(self.__on_scenario_complete)

    def __on_asterisk_stop(self, result):
        """Determines the overall pass/fail state for the test prior to
        shutting down the reactor.

        Keyword Arguments:
        result                 -- A twisted deferred object

        Returns:
        A twisted deferred object.
        """

        LOGGER.debug('{0} Calculating test results.'.format(self))

        for scenario in self.scenarios:
            self.test_object.set_passed(scenario.passed)
        return result

    def __on_scenario_complete(self, message):
        """Queries the scenarios to determine if the test is complete.

        Keyword Arguments:
        message                -- The event payload.
        """

        LOGGER.debug('{0} Quering test scenarios.'.format(self))

        for scenario in self.scenarios:
            if not scenario.finished:
                return

        LOGGER.debug('{0} Test case execution is complete.'.format(self))
        self.test_object.stop_reactor()

    def __validate_config(self, config):
        """Validates the module configuration for this test.

        Keyword Arguments:
        config                 -- The YAML configuration for this test.

        Returns:
        True if the configuration is valid, False otherwise.
        """

        LOGGER.debug('{0} Validating module configuration.'.format(self))

        if not config:
            LOGGER.error('{0} No configuration provided.'.format(self))
            return False

        if 'cli_command' not in config:
            msg = '{0} Configuration is missing required attribute \'{1}\'.'
            LOGGER.error(msg.format(self, 'cli_command'))
            return False

        if 're_query' not in config:
            msg = '{0} Configuration is missing required attribute \'{1}\'.'
            LOGGER.error(msg.format(self, 're_query'))
            return False

        for key in config.keys():
            k = key.lower()
            if k != 'cli_command' and k != 're_query':
                msg = '{0} Unsupported configuration attribute {1} specified.'
                LOGGER.error(msg.format(self, key))
                return False
        return True
