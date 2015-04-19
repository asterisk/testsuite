#!/usr/bin/env python
'''
Copyright (C) 2013, Digium, Inc.
Kevin Harwell <kharwell@digium.com>
George Joseph <george.joseph@fairview5.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys

sys.path.append("lib/python/asterisk")

from test_case import TestCase

class AMISendTest(TestCase):
    def __init__(self, path=None, config=None):
        super(AMISendTest, self).__init__(path, config)
        self.config = config
        self.action = config.get('ACTION')
        if not self.action:
            raise Exception('"ACTION" was not defined in test-config.yaml')
        self.create_asterisk()

    def run(self):
        super(AMISendTest, self).run()
        self.create_ami_factory()

    def ami_connect(self, ami):
        ami.sendDeferred(self.action).addCallback(self.__on_response)

    def __on_response(self, result):
        # stop test since done
        self.stop_reactor()

