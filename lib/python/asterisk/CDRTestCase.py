#!/usr/bin/env python
"""
Copyright (C) 2011, Digium Inc.
Jonathan Rose <jrose@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging
from twisted.internet import reactor
from twisted.internet.error import ReactorNotRunning

sys.path.append("lib/python")
from asterisk import Asterisk
from TestCase import TestCase
from cdr import AsteriskCSVCDR, AsteriskCSVCDRLine
from collections import defaultdict

logger = logging.getLogger(__name__)

class CDRTestCase(TestCase):
    """
    CDRTestCase is a subclass of the Asterisk TestCase intended to make tests involving CDR files easier.

    Example Usage:
    class TestFoo(CDRTestCase):
        def __init__(self):
            super(TestFoo, self).__init__()
            self.add_expectation("Master", AsteriskCSVCDRLine(
                accountcode='testsuite',
                source='',
                destination='1',
                dcontext='default',
                callerid='',
                channel='Local/1@default-.*',
                disposition='ANSWERED',
                amaflags='DOCUMENTATION'
            ))
        def main():
            test = TestFoo()
            test.start_asterisk()
            reactor.run()
            test.stop_asterisk()

            return test.results()
    """

    def __init__(self):
        """
        Create a single Asterisk instance.
        """
        super(CDRTestCase, self).__init__()
        self.CDRFileExpectations = defaultdict(list)
        self.create_asterisk()


    def add_expectation(self, recordname, cdrline):
        """
        Add an expectation to the expectation list

        Keyword Arguments:
        recordname -- name of the record in which the cdr line is expected to appear
        cdrline -- AsteriskCSVCDRLine for an expected element of the cdr

        Example Usage:
        self.add_expectation("Master", AsteriskCSVCDRLine(accountcode="",
            source="", destination="s", dcontext="default", callerid="",
            channel="SIP/test-00000000", disposition="CONGESTION",
            amaflags="DOCUMENTATION"))
        """
        self.CDRFileExpectations[recordname].append(cdrline)

    def match_cdrs(self):
        #Automatically invoked at the end of the test, this will test the CDR files against the listed expectations.
        self.passed = True

        for key in self.CDRFileExpectations:
            # We'll store the cdrlines for an individual cdr log file in here
            records = []

            # Build records with just the cdrlines that belong to this record
            for i in self.CDRFileExpectations.get(key):
                records.append(i)

            cdr_expect = AsteriskCSVCDR(records=records)
            cdr_file = AsteriskCSVCDR(fn="%s/%s/cdr-csv/%s.csv" % (self.ast[0].base, self.ast[0].directories['astlogdir'], key))

            if cdr_expect.match(cdr_file):
                logger.debug("%s.csv - CDR results met expectations" % key)
            else:
                logger.error("%s.csv - CDR results did not meet expectations.  Test Failed." % key)
                self.passed = False

    def results(self):
        """
        Returns the test results.

        Example Usage:
        def foo(self):
            test = bar()
            test.start_asterisk()
            reactor.run()
            test.stop_asterisk()
            return test.results()
        """

        self.match_cdrs()
        if self.passed == True:
            return 0
        return 1

    def ami_logoff(self, ami):
        """
        An AMI callback event.

        """
        self.stop_reactor()

    def ami_connect(self, ami):
        """
        An AMI callback event from create_ami_factory() function.
        """
        super(CDRTestCase, self).ami_connect(self)
        ami.registerEvent("Hangup", self.ami_test_done)

        self.ami[0].originate(
            channel = 'Local/1@default',
            application = 'Echo'
        ).addErrback(self.ami_logoff)

    def ami_test_done(self, ami, event):
        if event.get("event") == "Hangup":
            if self.no_active_channels():
                try:
                    self.stop_reactor()
                except ReactorNotRunning:
                    # No problemo.
                    pass

    def run(self):
        """
        Create an AMI factory with a calback for the ami_connect() function.
        """
        super(CDRTestCase, self).run()
        self.create_ami_factory()
