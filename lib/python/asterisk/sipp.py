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

from asterisk import Asterisk

logger = logging.getLogger(__name__)


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
        self.positional_args = tuple(positional_args) # don't allow caller to mangle his own list
        self.test_dir = test_dir
        self.default_port = 5061
        self.sipp = None

    def run(self):
        sipp_args = [
                'sipp', '127.0.0.1',
                '-sf', '%s/sipp/%s' % (self.test_dir, self.scenario['scenario'])
        ]
        default_args = {
            '-p' : self.default_port,
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

        logger.info("Executing SIPp scenario: %s" % self.scenario['scenario'])
        logger.info(sipp_args)

        self.sipp = subprocess.Popen(sipp_args,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def waitAndEvaluate(self):

        (out, err) = self.sipp.communicate()

        result = self.sipp.wait()
        logger.debug(out)
        if result:
            logger.warn("SIPp scenario FAILED")
            passed = False
            logger.warn(err)
        else:
            logger.info("SIPp scenario PASSED")
            passed = True

        return passed


class SIPpTest:
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

        working_dir - A path to the working directory to use for the temporary
            Asterisk instance.  This is typically a path to somewhere in /tmp.

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
        self.working_dir = working_dir
        self.test_dir = test_dir
        self.scenarios = scenarios
        self.sipp = []
        self.stdout = []
        self.stderr = []
        self.result = []

        self.ast1 = Asterisk(base=self.working_dir)
        self.ast1.install_configs('%s/configs/ast1' % self.test_dir)

    def __run_sipp(self, scenario, default_port):
        sipp_args = [
                'sipp', '127.0.0.1',
                '-sf', '%s/sipp/%s' % (self.test_dir, scenario['scenario'])
        ]
        default_args = {
            '-p' : default_port,
            '-m' : '1',
            '-i' : '127.0.0.1',
            '-timeout' : '20s'
        }

        # Override and extend defaults
        default_args.update(scenario)
        del default_args['scenario']

        for (key, val) in default_args.items():
            sipp_args.extend([ key, val ])

        logger.debug("Executing SIPp scenario: %s" % scenario['scenario'])
        logger.debug(sipp_args)

        return subprocess.Popen(sipp_args,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def run(self):
        """
        Run the test.

        Returns 0 for success, 1 for failure.
        """
        self.ast1.start()

        for s in self.scenarios:
            default_port = 5060 + len(self.sipp) + 1
            self.sipp.append(self.__run_sipp(s, str(default_port)))

        passed = True
        for i in range(len(self.sipp)):
            (out, err) = self.sipp[i].communicate()
            self.stdout.append(out)
            self.stderr.append(err)
            self.result.append(self.sipp[i].wait())
            if self.result[i]:
                logger.warn("SIPp scenario #%d FAILED" % i)
            else:
                logger.info("SIPp scenario #%d PASSED" % i)
            if self.result[i]:
                passed = False
                #print self.stdout[i]
                logger.warn(self.stderr[i])

        self.ast1.stop()

        if passed:
            return 0
        else:
            return 1

