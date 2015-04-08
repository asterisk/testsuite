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
sys.path.append("tests/rest_api/applications")

from asterisk.test_case import TestCase
from twisted.internet import reactor, defer

LOGGER = logging.getLogger(__name__)


class StasisStatusTestCase(TestCase):
    """The test case.

    This class serves as a harness for the test scenarios. It manages the
    life-cycle of the the objects needed to execute the test plan.
    """

    def __init__(self, scenario_builder):
        """Constructor.

        scenario_builder       -- The builder to use for constructing
                                  the test scenarios.

        """

        super(StasisStatusTestCase, self).__init__()

        self.create_asterisk()

        self.__host = self.ast[0].host
        self.__port = 8088
        self.__credentials = ('testsuite', 'testsuite')

        self.__scenarios = list()
        self.__iterator = None
        self.__builder = scenario_builder

        reactor.run()
        return

    def __format__(self, format_spec):
        """Overrides default format handling for 'self'."""

        return self.__class__.__name__ + ':'

    def ami_connect(self, ami):
        """Handler for the AMI connect event.

        Keyword Arguments:
        ami                    -- The AMI instance that raised this event.
        """

        super(StasisStatusTestCase, self).ami_connect(ami)
        self.__initialize_scenarios(ami)

    def __get_next_scenario(self):
        """ Gets the next scenario from the list."""

        scenario = None
        try:
            scenario = self.__iterator.next()
        except StopIteration:
            pass
        return scenario

    def __initialize_scenarios(self, ami):
        """Initializes the scenarios.

        Keyword Arguments:
        ami                    -- The AMI instance for this test.
        """

        deferred = defer.Deferred()
        self.__scenarios = self.__builder(ami,
                                          self.__host,
                                          self.__port,
                                          self.__credentials)
        self.__iterator = iter(self.__scenarios)

        for scenario in self.__scenarios:
            deferred.addCallback(self.__try_run_scenario)

        deferred.callback(self.__get_next_scenario())

    def on_reactor_timeout(self):
        """Called when the reactor times out"""

        LOGGER.warn("{0} Reactor is timing out. Setting test to FAILED.")
        self.set_passed(False)

    def __on_scenario_complete(self, sender, message):
        """Queries the scenarios to determine if it is time to shut down
        the test.

        Keyword Arguments:
        sender                 -- The object that raised the event.
        message                -- The event payload.
        """

        sender.stop()
        for scenario in self.__scenarios:
            if not scenario.finished:
                return

        LOGGER.debug('{0} Test case execution is complete.'.format(self))
        self.stop_reactor()

    def run(self):
        """Executes the test case.

        Tries to set up the state needed by the test. If successful, the test
        is executed and then the test state is torn down."""

        LOGGER.debug('{0} Starting test case execution.'.format(self))
        super(StasisStatusTestCase, self).run()

        self.create_ami_factory()

    def stop_reactor(self):
        """Clean up actions to perform prior to shutting down the reactor.

        Queries the scenarios for their pass/fail state to determine
        overall pass/fail state for the test. Then, destroys the test state
        before stopping the reactor."""

        LOGGER.debug('{0} Stopping reactor.'.format(self))
        for scenario in self.__scenarios:
            self.set_passed(scenario.passed)
            if not scenario.clean:
                scenario.stop()
        super(StasisStatusTestCase, self).stop_reactor()
        LOGGER.debug('{0} Reactor stopped.'.format(self))

    def __try_run_scenario(self, scenario):
        """Starts the stasis scenario.

        Keyword Arguments:
        scenario               -- The scenario to try to start.

        Returns:
        If the self.__iterator has not yet finished traversing the list,
        returns the next scenario in self.__scenarios.

        Otherwise,returns None.
        """

        msg = '{0} {1} scenario [{2}]'

        if scenario is not None:
            LOGGER.debug((msg + '.').format(self,
                                            'Starting',
                                            scenario.name))
            scenario.start(self.__on_scenario_complete)
            return self.__get_next_scenario()

        msg = msg + '; {3}.'
        LOGGER.warn(msg.format(self,
                               'Cannot connect',
                               None,
                               'scenario has not been assigned a value.'))
        return None
