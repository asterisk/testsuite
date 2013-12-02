#!/usr/bin/env python
'''
Copyright (C) 2013, Digium, Inc.
Kevin Harwell <kharwell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import time

sys.path.append("lib/python/asterisk")

from sipp import SIPpTestCase

ACTION = {
    "Action":"PJSIPShowSubscriptionsInbound"
}

class AMISendTest(SIPpTestCase):
    def __init__(self, path=None, config=None):
        super(AMISendTest, self).__init__(path, config)

    def run(self):
        super(AMISendTest, self).run()

    def ami_connect(self, ami):
        super(AMISendTest, self).ami_connect(ami)
        # give some time for everything to subscribe
        time.sleep(3)
        ami.sendDeferred(ACTION).addCallback(ami.errorUnlessResponse)
