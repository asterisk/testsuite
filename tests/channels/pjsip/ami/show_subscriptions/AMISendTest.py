#!/usr/bin/env python
'''
Copyright (C) 2013, Digium, Inc.
Kevin Harwell <kharwell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging

sys.path.append("lib/python/asterisk")

from sipp import SIPpScenario
from test_case import TestCase

from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)

ACTION = {
    "Action":"PJSIPShowSubscriptionsInbound"
}

class AMISendTest(TestCase):
    def __init__(self, path=None, config=None):
        self.updates_received = 0
        super(AMISendTest, self).__init__(path, config)
        self.create_asterisk()

    def run(self):
        super(AMISendTest, self).run()
        self.create_ami_factory()

    def ami_connect(self, ami):
        super(AMISendTest, self).ami_connect(ami)

	ami.registerEvent("TestEvent", self.test_event)
        LOGGER.info('Starting subscription scenario')
        sipp = SIPpScenario(self.test_name,
            {'scenario':'subscribe.xml', '-p':'5061' })
        sipp.run(self)

    def test_event(self, ami, event):
        if event['state'] != "SUBSCRIPTION_STATE_SET" \
            or event['statetext'] != "ACTIVE" \
            or event['endpoint'] != "user1":
            return

        self.updates_received += 1
        if self.updates_received != 2:
            return

        LOGGER.info('Getting inbound subscriptions...')
        ami.sendDeferred(ACTION).addCallback(ami.errorUnlessResponse)
        reactor.callLater(2, self.stop_reactor)
