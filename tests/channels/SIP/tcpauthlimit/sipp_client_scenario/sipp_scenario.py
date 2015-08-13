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
sys.path.append("tests/channels/SIP/tcpauthlimit/sipp_client_scenario")

from sipp import SIPpScenario
from twisted.internet import defer

LOGGER = logging.getLogger(__name__)


class SIPpScenarioWrapper(SIPpScenario):
    """Wrapper class for a SIPpScenario.

    This class provides the ability to override the default results evaluation
    mechanism of the SIPpScenario as specified in the test module configuration.
    """

    def __init__(self, test_dir, scenario, positional_args=(),
                 target='127.0.0.1', scenario_id=None):
        """Constructor.

        Keyword Arguments:
        test_dir               -- The path to the directory containing the test
                                  module.
        scenario               -- The SIPp scenario to execute (dictionary).
        positional_args        -- SIPp non-standard parameters (those that can
                                  be specified multiple times, or take multiple
                                  arguments (iterable). Optional.
                                  Default: Empty iterable.
        target                 -- The address for the remote host. Optional.
                                  Default: 127.0.0.1.
        scenario_id            -- The scenario_id for this scenario. Used for
                                  logging. If nothing is provided, the id will
                                  be the value of scenario['scenario'].
                                  Optional. Default: None.
        """

        self.__scenario_id = scenario_id or scenario['scenario']

        self.__running = False
        self.__actual_result = None
        self.__expected_result = None
        self.__on_complete = None
        self.__passed = None

        SIPpScenario.__init__(self,
                              test_dir,
                              scenario,
                              positional_args,
                              target)

    def adjust_result(self, expected_result=None):
        """Adjusts the pass/fail status for the scenario.

        Keyword Arguments:
        expected_result        -- The expected SIPp exec result. If not
                                  provided, the results will be analyzed as/is,
                                  with no adjustments applied.
                                  Optional. Default: None.
        """

        msg = '{0} Adjusting scenario results...'
        LOGGER.debug(msg.format(self))

        if self.__actual_result is None:
            msg = '{0} Can\'t adjust results; {1}'
            if self.__running:
                msg.format(self, 'I am still running the SIPp scenario.')
            else:
                msg.format(self, 'I haven\'t run the SIPp scenario yet.')
            LOGGER.debug(msg)
            return

        if expected_result is None:
            self.__expected_result = self.__actual_result
        else:
            self.__expected_result = expected_result

        if not self.passed:
            msg = '{0} Scenario failed.\n'
            msg += '\tBased on the test configuration,'
            msg += ' I expected to receive:\n'
            msg += '\t\tSIPp exit code:\t{1}\n'
            msg += '\tHere is what I actually received:\n'
            msg += '\t\tSIPp exit code:\t{2}\n'
            LOGGER.error(msg.format(self,
                                    self.__expected_result,
                                    self.__actual_result))
        else:
            LOGGER.info('{0} Congrats! Scenario passed.'.format(self))

    def __format__(self, format_spec):
        """Overrides default format handling for 'self'."""

        return self.__class__.__name__ + ' [' + self.__scenario_id + ']:'

    def run(self):
        """Execute a SIPp scenario passed to this object.

        Returns:
        A twisted.internet.defer.Deferred instance that can be used to
        determine when the SIPp Scenario has exited.
        """

        def __handle_results(result):
            """Handles scenario results post-processing.

            Keyword Arguments:
            result             -- The SIPp exec result.
            """

            msg = '{0} SIPp execution complete.'
            LOGGER.debug(msg.format(self))

            self.__running = False
            self.__actual_result = self.result.exitcode
            self.__on_complete.callback(result)

        self.__running = True
        self.__setup_state()

        LOGGER.debug('{0} Starting SIPp execution'.format(self))
        deferred = SIPpScenario.run(self)
        deferred.addCallback(__handle_results)
        return self.__on_complete

    def __setup_state(self):
        """Initialize the scenario state."""

        self.__passed = False
        self.__actual_result = None
        self.__expected_result = None
        self.__on_complete = defer.Deferred()

    @property
    def passed(self):
        """Evaluates SIPp exit code for the pass/fail status.

        Returns:
        True if the SIPp exit code matched the expected result.
        False otherwise.
        """

        if self.__actual_result is None or self.__expected_result is None:
            return self.__passed
        return self.__actual_result == self.__expected_result

    @passed.setter
    def passed(self, value):
        """Overrides setting the pass/fail value for this scenario."""

        self.__passed = value

    @property
    def scenario_id(self):
        """Returns the scenario_id for this scenario."""

        return self.__scenario_id
