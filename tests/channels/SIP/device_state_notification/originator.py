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
    'RINGING',
    'INUSE',
    'NOT_INUSE'
]

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
        self.ami.registerEvent('ExtensionStatus', self.extension_status)
        return

    def extension_status(self, ami, event):
        if event['hint'] != 'Custom:Eggs':
            return

        LOGGER.info("Extension state changed to {0}".format(event['status']))
        self.current_destination += 1
        if self.current_destination < len(DESTINATIONS):
            self.originate_call()

    def originate_call(self):

        LOGGER.info("Originating call to %s" %
                DESTINATIONS[self.current_destination])

        self.ami.originate(channel='Local/%s@default' %
                DESTINATIONS[self.current_destination],
                application='Echo')

    def scenario_started(self, result):
        def failure(result):
            self.test_object.set_passed(False)
            return result

        self.originate_call()
        return result
