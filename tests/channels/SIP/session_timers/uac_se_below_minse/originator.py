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

class Originator(object):
    def __init__(self, module_config, test_object):
        self.ami = None
        test_object.register_ami_observer(self.ami_connect)
        test_object.register_scenario_started_observer(self.scenario_started)
        self.test_object = test_object
        self.current_destination = 0
        return

    def ami_connect(self, ami):
        LOGGER.info("AMI connected")
        self.ami = ami
        return

    def success(self, result):
        LOGGER.info("Originate Successful")
        return result

    def originate_call(self):

        LOGGER.info("Originating call")

        self.ami.originate(channel = 'Local/s@default',
                application = 'Echo').addCallback(self.success)

    def scenario_started(self, result):
        def failure(result):
            self.test_object.set_passed(False)
            return result

        self.originate_call()
        return result
