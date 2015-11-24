#!/usr/bin/env python
'''
Copyright (C) 2015, Digium, Inc.
Kevin Harwell <kharwell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging
import sys
import time

sys.path.append("lib/python/asterisk")

from twisted.internet import reactor
from sipp import SIPpScenario
from test_case import TestCaseModule

LOGGER = logging.getLogger(__name__)


class DNSCacheTestModule(TestCaseModule):
    """Test case for dns cache"""

    def __init__(self, test_path='', test_config=None):
        """Constructor."""

	test_config['connect-ami'] = True
        super(DNSCacheTestModule, self).__init__(test_path, test_config)

    def ami_connect(self, ami):
        """Wait for the presence state to change then issue a subscribe."""

        def __originate_call(num=[0]):
            """Originate a call using sipp"""
            num[0] += 1
            sipp = SIPpScenario(self.test_name, {
                'scenario':'invite.xml', '-p':'506' + str(num[0])})
            return sipp.run(self)

        def __check_output(cli):
            """Verify the CLI show cache command works"""
            LOGGER.info("\n%s\n", cli.output)
            self.set_passed('invalid.dns' in cli.output)
            self.stop_reactor()

        def __on_test_event(ami, event, num=[0]):
            if event['state'] == 'DNS_CACHE_HIT':
                num[0] += 1
                if num[0] == 2:
                    # on first "hit" - wait for entry to expire (should be 60
                    # secs) and then try again (should cause a "miss")
                    reactor.callLater(65, __originate_call)
                elif num[0] == 4 and event['numattempts'] == '2':
                    self.ast[0].cli_exec(
                        'dns cache show').addCallback(__check_output)
            if event.get('state') == 'DNS_CACHE_UPDATE':
                # the domain name should be in the cache now (or updated),
                # so try again and this time we should get a "hit"
                __originate_call()

        ami.registerEvent('TestEvent', __on_test_event)

        # the first call should not resolve, thus get added to the cache
        __originate_call()
