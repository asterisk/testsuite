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
        super(AMISendTest, self).__init__(path, config)
        self.create_asterisk()

    def run(self):
        super(AMISendTest, self).run()
        self.create_ami_factory()

    def ami_connect(self, ami):
        super(AMISendTest, self).ami_connect(ami)

        def _send_show_subscriptions(obj):
            LOGGER.info('Getting inbound subscriptions...')
            ami.sendDeferred(ACTION).addCallback(ami.errorUnlessResponse)
            reactor.callLater(2, self.stop_reactor)
            return obj

        LOGGER.info('Starting subscription scenario')
        sipp = SIPpScenario(self.test_name,
            {'scenario':'subscribe.xml', '-p':'5061' })
        sipp.run(self).addCallback(_send_show_subscriptions)
