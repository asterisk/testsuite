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

from test_case import TestCase
from sipp import SIPpScenario

LOGGER = logging.getLogger(__name__)

ACTION = {
    "Action":"PJSIPShowRegistrationsInbound"
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

        def _on_register(obj):
            LOGGER.info('Getting inbound registrations...')
            ami.sendDeferred(ACTION).addCallback(self.__on_response)
            return obj

        LOGGER.info('Starting inbound registration scenario')

        sipp = SIPpScenario(self.test_name,
            {'scenario':'register.xml', '-p':'5061' })
        sipp.run(self).addCallback(_on_register)

    def __on_response(self, result):
        # stop test since done
        self.stop_reactor()
