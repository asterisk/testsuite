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

from asterisk import Asterisk


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

        print "Executing SIPp scenario: %s" % scenario['scenario']

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
                print "SIPp scenario #%d FAILED"
            else:
                print "SIPp scenario #%d PASSED"
            if self.result[i]:
                passed = False
                #print self.stdout[i]
                print self.stderr[i]

        self.ast1.stop()

        if passed:
            return 0
        else:
            return 1

