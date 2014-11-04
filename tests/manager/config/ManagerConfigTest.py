#!/usr/bin/env python
'''
Copyright (C) 2014, Fairview 5 Engineering, LLC
George Joseph <george.joseph@fairview5.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import os
import logging

sys.path.append("lib/python")

from test_case import TestCase
from syncami import SyncAMI

LOGGER = logging.getLogger(__name__)

class ManagerConfigTest(TestCase):
    def __init__(self, path=None, config=None):
        super(ManagerConfigTest, self).__init__(path, config)
        self.create_asterisk()
        self.config = config

    def run(self):
        super(ManagerConfigTest, self).run()
        self.passed = True

        try:
            self.syncami = SyncAMI()
            for x in self.config.get('ami-config'):
                self.run_test(x)
                if (not self.passed):
                    break
            self.syncami.logoff()
        except Exception as e:
            self.passed = False
            LOGGER.error("Exception caught: %s" % e)
            raise
        finally:
            self.stop_reactor()

    def run_test(self, test):
        message = test.get('message')
        res = self.syncami.send(message)
        self.process_response(test, res, message)

    def process_response(self, test, actual, message):
        expected = test.get('expected')

        if actual.get('Response') != expected.get('Response'):
            LOGGER.error("Request failed...\nMessage: %s\n\nExpected: %s\n\nActual: %s" % (message, expected, actual.items()))
            self.passed = False
            return

        for name, evalue in expected.items():
            if name == 'Payload':
                avalue = actual.get_payload().strip()
            else:
                avalue = actual.get(name)

            if avalue != evalue:
                LOGGER.error("'%s' was '%s' instead of '%s'...\nMessage: %s\n\nExpected: %s\n\nActual: %s" %\
                    (name, avalue, evalue, message, expected, actual.items()))
                self.passed = False
                break
