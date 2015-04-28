#!/usr/bin/env python
"""
Copyright (C) 2015, Digium, Inc.
Ashley Sanders <asanders@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging
import re

sys.path.append("lib/python")
sys.path.append("tests/channels/pjsip/configuration")

LOGGER = logging.getLogger(__name__)


class TestScenario(object):
    """The test scenario.

    This class is responsible for executing the test strategy and reporting
    the test results.
    """

    def __init__(self, cli_command, output_query, on_complete=None):
        """Constructor.

        Keyword Arguments:
        cli_command            -- The CLI command to execute.
        output_query           -- The regex query to use to search the output
                                  of the CLI command.
        on_complete            -- The callback to invoke when the scenario has
                                  completed executing (optional) (default None).
        """

        LOGGER.debug('{0} Initializing test scenario'.format(self))
        self.__cli_command = cli_command
        self.__output_query = output_query
        self.__on_complete = on_complete
        self.__passed = None

    def __format__(self, format_spec):
        """Overrides default format handling for 'self'."""

        return self.__class__.__name__ + ':'

    def __parse_cli_output(self, cli):
        """Parses the CLI command output to determine if the res_pjsip.so
        module is loaded.

        Keyword Arguments:
        cli                    -- The AsteriskCliCommand instance containing
                                  the CLI executed command and its output.

        Returns:
        An AsteriskCliCommand instance.
        """

        command = cli.cli_cmd
        output = cli.output

        LOGGER.debug('{0} Parsing CLI Command Output.'.format(self))
        LOGGER.debug('{0} CLI Command: {1}'.format(self, command))
        LOGGER.debug('{0} CLI Output: {1}'.format(self, output))

        query_results = re.search(self.__output_query, output)
        self.passed = query_results is not None
        return cli

    def run(self, ast):
        """Runs the scenario.

        Keyword Arguments:
        ast                    -- The Asterisk instance for this scenario.

        Returns:
        A twisted deferred instance.
        """

        LOGGER.debug('{0} Running test scenario.'.format(self))

        cli_deferred = ast.cli_exec(self.__cli_command)
        cli_deferred.addCallback(self.__parse_cli_output)
        if self.__on_complete is not None:
            cli_deferred.addCallback(self.__on_complete)
        return cli_deferred

    @property
    def finished(self):
        """Whether or not the this scenario has finished execution.

        Returns:
        True if the scenario has finished execution, False otherwise.
        """

        return self.__passed is not None

    @property
    def passed(self):
        """The results of the scenario.

        Returns:
        False if the scenario has not finished execution. Else, True if the
        scenario was successful, False otherwise.
        """

        return False if not self.finished else self.__passed

    @passed.setter
    def passed(self, value):
        """Safely set the passed variable for this scenario."""

        if self.__passed is False:
            return

        self.__passed = value
        return
