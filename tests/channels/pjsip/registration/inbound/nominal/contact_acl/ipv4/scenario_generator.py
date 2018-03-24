#!/usr/bin/env python
'''
Copyright (C) 2014, Digium, Inc.
Jonathan Rose <jrose@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging

sys.path.append("lib/python")

from asterisk import test_suite_utils
from asterisk.sipp import ScenarioGenerator

LOGGER = logging.getLogger(__name__)


class IPv4ScenarioGenerator(ScenarioGenerator):
    """SIPp Scenario Generator - Creates scenarios that originate from an IPv4
    loopback address and a broadcast capable IPv4 address using UDP and TCP
    """

    def generator(self):
        """Determines bindable address and yields the scenario list
        """
        using_addr = test_suite_utils.get_bindable_ipv4_addr()

        if not using_addr:
            LOGGER.error("Failed to find a suitable IPv4 address.")
            return

        LOGGER.info("Selected ipv4 address: %s" % using_addr)

        yield {'scenarios': [
            {
                'key-args': {
                    'scenario': 'register-noauth-permitted.xml',
                    '-i': using_addr,
                    '-p': '5061',
                    '-s': 'alice'
                }
            },
            {
                'key-args': {
                    'scenario': 'register-noauth-permitted.xml',
                    '-i': using_addr,
                    '-p': '5062',
                    '-s': 'bob', '-t': 't1'
                }
            },
            {
                'key-args': {
                    'scenario': 'register-noauth-denied.xml',
                    '-i': '127.0.0.1',
                    '-p': '5063',
                    '-s': 'charlie'
                }
            },
            {
                'key-args': {
                    'scenario': 'register-noauth-denied.xml',
                    '-i': '127.0.0.1',
                    '-p': '5064',
                    '-s': 'carol', '-t': 't1'
                }
            }
        ]}

        return


class ScenarioGeneratorModule(object):
    """Pluggable module for SIPpTestCase to set the scenario
    generator to the one provided for this test.
    """
    def __init__(self, module_config, test_object):
        scenario_generator = IPv4ScenarioGenerator()
        test_object.register_scenario_generator(scenario_generator)

