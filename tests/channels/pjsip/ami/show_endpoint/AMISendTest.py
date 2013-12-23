#!/usr/bin/env python
'''
Copyright (C) 2013, Digium, Inc.
Kevin Harwell <kharwell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys

sys.path.append("lib/python/asterisk")

from TestCase import TestCase

ACTION = {
    "Action":"PJSIPShowEndpoint",
    "Endpoint":"user1"
}

class AMISendTest(TestCase):
    def __init__(self, path=None, config=None):
        super(AMISendTest, self).__init__(path, config)
        self.create_asterisk()

    def run(self):
        super(AMISendTest, self).run()
        self.create_ami_factory()

    def ami_connect(self, ami):
        ami.sendDeferred(ACTION).addCallback(self.__on_response)

    def __on_response(self, result):
        # stop test since done
        self.stop_reactor()

