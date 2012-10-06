#!/usr/bin/env python
'''
Copyright (C) 2012, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging

sys.path.append("lib/python")

LOGGER = logging.getLogger(__name__)

DESTINATIONS = [
    'test1',
    'test2',
    'test3',
    'test4',
    'test5',
    'test6',
]

class Originator(object):
    def __init__(self, module_config, test_object):
        test_object.register_ami_observer(self.ami_connect)
        test_object.register_scenario_started_observer(self.scenario_started)
        self.test_object = test_object
        self.current_destination = 0

    def ami_connect(self, ami):
        LOGGER.info("AMI connected")
        self.ami = ami

    def success(self, result):
        LOGGER.info("Originate Successful")
        self.current_destination += 1

    def originate_call(self):
        def failure(result):
            self.test_object.set_passed(False)
            return result

        dest = DESTINATIONS[self.current_destination]

        LOGGER.info("Originating call to %s" % dest)

        deferred = self.ami.originate(channel='Local/%s@default' % dest,
                application='Echo')
        deferred.addCallback(self.success).addErrback(failure)

    def scenario_started(self, result):
        LOGGER.info("Scenario started. Originating call")
        self.originate_call()
        return result
