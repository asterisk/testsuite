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

from abc import ABCMeta, abstractmethod
from stasisstatus.observable_object import ObservableObject

LOGGER = logging.getLogger(__name__)


class TestScenario(ObservableObject):
    """The test scenario.

    This class is responsbile for presenting a facade around the
    AriClient and TestStrategy objects.
    """

    __metaclass__ = ABCMeta

    def __init__(self, ami, ari_client, monitor, expected, name='testsuite'):
        """Constructor.

        Keyword Arguments:
        ami                    -- The AMI instance for this TestScenario.
        ari_client             -- The AriClient to use to for executing the
                                  TestStrategy commands.
        monitor                -- The ChannelVariableMonitor instance for this
                                  TestScenario.
        expected               -- The expected value for this TestScenario.
        name                   -- The name for this TestScenario instance
                                  (optional) (default 'testsuite').
        """

        super(TestScenario, self).__init__(name, ['on_complete',
                                                  'on_start',
                                                  'on_stop'])
        self.__ami = ami
        self.__ari_client = ari_client
        self.__actual_value = None
        self.__expected_value = expected
        self.__monitor = monitor
        self.__passed = None
        self.__delayed = False
        self.__monitor.suspend()
        self.ari_client.register_observers('on_client_start',
                                           self.on_ari_client_start)
        self.ari_client.register_observers('on_client_stop',
                                           self.on_ari_client_stop)
        self.monitor.register_observers('on_value_changed',
                                        self.on_monitor_on_value_changed)

    def compile_results(self):
        """Compiles the results after executing the test strategy."""

        if self.finished:
            return

        LOGGER.debug('{0} Compiling the results.'.format(self))

        passed = self.actual_value == self.expected_value

        LOGGER.debug('{0} Test strategy is complete.'.format(self))
        LOGGER.debug('{0} Test values: Expected [{1}]; Actual [{2}].' \
            .format(self, self.expected_value, self.actual_value))
        LOGGER.debug('{0} Test results: Test {1}.' \
            .format(self, 'Passed' if passed else 'Did Not Pass'))

        self.passed = passed

    def finish_scenario(self):
        """Performs the final tasks."""

        if self.finished:
            LOGGER.debug('{0} Scenario is already finished.'.format(self))

        self.suspend()
        LOGGER.debug('{0} Finishing the scenario.'.format(self))
        self.compile_results()

    def on_ari_client_start(self, sender, message):
        """Handles the AriClient on_client_start event.

        Keyword Arguments:
        sender                 -- The object that raised the event.
        message                -- The event payload.
        """

        LOGGER.debug('{0} AriClient started successfully.'.format(self))
        self.notify_observers('on_start', None, True)
        self.__try_run()

    def on_ari_client_stop(self, sender, message):
        """Handler for the AriClient on_client_stop event.

        Keyword Arguments:
        sender                 -- The object that raised the event.
        message                -- The event payload.
        """

        LOGGER.debug('{0} Scenario has stopped.'.format(self))
        self.notify_observers('on_stop', None, True)

    def on_monitor_on_value_changed(self, sender, message):
        """Handles the ChannelVariableMonitor 'on_value_changed' event.

        Keyword Arguments:
        sender                 -- The object that raised the event.
        message                -- The event payload.
        """

        msg = '{0} '.format(self)

        if self.suspended:
            LOGGER.debug(msg + 'Scenario is suspended.')
            return

        self.actual_value = self.monitor.captured_value

        if self.actual_value == self.expected_value:
            self.suspend()
            LOGGER.debug('{0} Looks like we made it.'.format(self))
            self.finish_scenario()

    def resume(self):
        """Overrides the default behavior of resetting the value of the
        suspended flag."""

        #Run the 'resume' logic first, then do the delayed check.
        if self.suspended:
            super(TestScenario, self).resume()
            self.__monitor.resume()

        if not self.suspended and self.__delayed:
            self.__try_run()

    @abstractmethod
    def run_strategy(self):
        """Runs the Test Scenario."""

        return

    def start(self):
        """Starts the test scenario."""

        LOGGER.debug('{0} Starting scenario.'.format(self))
        self.ari_client.start()

    def stop(self):
        """Stops the scenario execution and tears down its state."""

        if self.ari_client.suspended:
            return

        LOGGER.debug('{0} Stopping the scenario.'.format(self))
        self.suspend()
        self.ari_client.stop()

    def suspend(self):
        """Overrides the default behavior of setting the value of the
        suspended flag."""

        if self.suspended:
            return

        super(TestScenario, self).suspend()
        self.__monitor.suspend()

    def __try_run(self):
        """Runs this strategy. Only to be called when this scenario is not
        suspended and after the ARI client has connected."""

        if not self.suspended:
            self.__delayed = False
            LOGGER.debug('{0} Running scenario.'.format(self))
            self.run_strategy()
        else:
            self.__delayed = True

    @property
    def actual_value(self):
        """The actual value for this TestScenario."""

        return self.__actual_value

    @actual_value.setter
    def actual_value(self, value):
        """Sets the actual value for this TestScenario."""

        self.__actual_value = value

    @property
    def ami(self):
        """The AMI instance for this TestScenario."""

        return self.__ami

    @property
    def ari_client(self):
        """The AriClient instance for this TestScenario."""

        return self.__ari_client

    @property
    def clean(self):
        """Flag indicating that this scenario has been torn down."""

        return self.ari_client.clean

    @property
    def expected_value(self):
        """The expected value for this TestScenario."""

        return self.__expected_value

    @property
    def finished(self):
        """Whether or not the strategy for this scenario has completed
        execution.

        Returns:
        True if the strategy has completed execution, False otherwise.
        """

        return self.__passed is not None

    @property
    def monitor(self):
        """The ChannelVariableMonitor instance."""

        return self.__monitor

    @property
    def passed(self):
        """The state of the strategy.

        Returns:
        None if the test strategy has not completed. Else, True if the test
        strategy was successful, False otherwise.
        """

        return False if not self.finished else self.__passed

    @passed.setter
    def passed(self, value):
        """Safely set the passed variable for this scenario."""

        if self.__passed is False:
            return

        self.__passed = value
        self.notify_observers('on_complete', None, True)
        return
