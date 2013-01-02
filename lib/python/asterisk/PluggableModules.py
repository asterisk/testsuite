#!/usr/bin/env python
'''
Copyright (C) 2012, Digium, Inc.
Kinsey Moore <kmoore@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging

sys.path.append("lib/python")

LOGGER = logging.getLogger(__name__)

class Originator(object):
    def __init__(self, module_config, test_object):
        '''Initialize config and register test_object callbacks.'''
        self.ami = None
        test_object.register_ami_observer(self.ami_connect)
        test_object.register_scenario_started_observer(self.scenario_started)
        self.test_object = test_object
        self.current_destination = 0
        self.config = {
            'channel': 'Local/s@default',
            'application': 'Echo',
            'data': '',
            'context': '',
            'exten': '',
            'priority': '',
            'ignore-originate-failure': 'no',
            'trigger': 'scenario_start',
            'id': 0
        }

        # process config
        if not module_config:
            return
        for k in module_config.keys():
            if k in self.config:
                self.config[k] = module_config[k]
        return

    def ami_connect(self, ami):
        '''Handle new AMI connections.'''
        LOGGER.info("AMI %s connected" % (str(ami.id)))
        if ami.id == self.config['id']:
            self.ami = ami
            if self.config['trigger'] == 'ami_connect':
                self.originate_call()
        return

    def failure(self, result):
        '''Handle origination failure.'''

        if self.config['ignore-originate-failure'] == 'no':
            LOGGER.info("Originate failed: %s" % (str(result)))
            self.test_object.set_passed(False)
        return None

    def originate_call(self):
        '''Handle origination of the call based on the options provided in the configuration.'''
        LOGGER.info("Originating call")

        if len(self.config['context']) > 0:
            self.ami.originate(channel = self.config['channel'], context = self.config['context'],
                exten = self.config['exten'], priority = self.config['priority']).addErrback(self.failure)
        else:
            self.ami.originate(channel = self.config['channel'], application = self.config['application'],
                data = self.config['data']).addErrback(self.failure)

    def scenario_started(self, result):
        '''Handle origination on scenario start if configured to do so.'''
        LOGGER.info("Scenario started")

        if self.config['trigger'] == 'scenario_start':
            self.originate_call()
        return result
