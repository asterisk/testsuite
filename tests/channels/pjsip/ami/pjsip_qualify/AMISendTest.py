#!/usr/bin/env python
'''
Copyright (C) 2013-2014, Digium, Inc.
Kevin Harwell <kharwell@digium.com>
Modified by Scott Emidy <jemidy@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging

sys.path.append("lib/python/asterisk")

from twisted.internet import reactor
from test_case import TestCase
from sipp import SIPpScenario

LOGGER = logging.getLogger(__name__)

ACTION = {
    "Action": "PJSIPQualify",
    "Endpoint": "user1"
}


class AMISendTest(TestCase):
    """Sends the AMI Action PJSIPQualify"""
    def __init__(self, path=None, config=None):
        """Constructor """
        super(AMISendTest, self).__init__(path, config)
        self.create_asterisk()
        self.passed = False  #This is default but it doesn't hurt to be explicit

    def run(self):
        super(AMISendTest, self).run()
        self.create_ami_factory()

    def ami_connect(self, ami):
        """Starts the PJSIPQualify scenario and Runs Through the XML"""
        super(AMISendTest, self).ami_connect(ami)

        def _ami_action():
            """ This Sends the PJSIPQualify Action """
            LOGGER.info('Sending PJSIPQualify Action...')
            ami.sendDeferred(ACTION).addCallback(ami.errorUnlessResponse)

        LOGGER.info('Starting PJSIPQualify scenario')

        sipp_options = (SIPpScenario(self.test_name,
                        {'scenario': 'options.xml', '-p': '5062'}))
        sipp_options.run(self).addCallback(self.__on_return)
        reactor.callLater(1,_ami_action)

    def __on_return(self, result):
        """Stops and Passes the Test if it Ran Successfully"""
        self.passed = result.passed
        self.stop_reactor()
