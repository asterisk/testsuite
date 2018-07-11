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


class IPv6ScenarioGenerator(ScenarioGenerator):
    """SIPp Scenario Generator - Creates scenarios that originate from an IPv6
    loopback address and a bindable non Link-Local address using UDP and TCP
    """

    def generator(self):
        """Determines bindable address and yields the scenario list
        """
        using_addr = test_suite_utils.get_bindable_ipv6_addr()

        if not using_addr:
            LOGGER.error("Failed to find a usable address for the test.")
            return

        using_addr = "[%s]" % using_addr

        LOGGER.info("Selected ipv6 address: %s" % using_addr)

        yield {'scenarios': [
            {
                'key-args': {
                    'scenario': 'register-noauth-permitted.xml',
                    '-i': using_addr,
                    '-p': '5061',
                    '-s': 'alice',
                    'target': '[::1]'
                }
            },
            {
                'key-args': {
                    'scenario': 'register-noauth-permitted.xml',
                    '-i': using_addr,
                    '-p': '5062',
                    '-s': 'bob',
                    '-t': 't1',
                    'target': '[::1]'
                }
            },
            {
                'key-args': {
                    'scenario': 'register-noauth-denied.xml',
                    '-i': '[::1]',
                    '-p': '5063',
                    '-s': 'charlie',
                    'target': '[::1]'
                }
            },
            {
                'key-args': {
                    'scenario': 'register-noauth-denied.xml',
                    '-i': '[::1]',
                    '-p': '5064',
                    '-s': 'carol',
                    '-t': 't1',
                    'target': '[::1]'
                }
            }
        ]}

        return


class ScenarioGeneratorModule(object):
    """Pluggable module for SIPpTestCase to set the scenario
    generator to the one provided for this test.
    """
    def __init__(self, module_config, test_object):
        scenario_generator = IPv6ScenarioGenerator()
        test_object.register_scenario_generator(scenario_generator)

