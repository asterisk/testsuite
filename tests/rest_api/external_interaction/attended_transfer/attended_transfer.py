'''
Copyright (C) 2014, Digium, Inc.
Joshua Colp <jcolp@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging
from sys import path

from sipp import SIPpScenario

LOGGER = logging.getLogger(__name__)


def on_kickoff_start(test_object, triggered_by, ari, event):
    LOGGER.debug("on_kickoff_start(%r)" % event)

    def _start_referer_scenario(referer_scenario, test_object):
        referer_scenario.run(test_object)

    sipp_referer = SIPpScenario(test_object.test_name,
                                {'scenario': 'referer.xml',
                                 '-p': '5065',
                                 '-3pcc': '127.0.0.1:5064'},
                                target='127.0.0.1')
    sipp_referee = SIPpScenario(test_object.test_name,
                                {'scenario': 'referee.xml',
                                 '-p': '5066',
                                 '-3pcc': '127.0.0.1:5064'},
                                target='127.0.0.1')

    sipp_referee.run(test_object)

    # The 3pcc scenario that first uses sendCmd (sipp_referer) will establish
    # a TCP socket with the other scenario (sipp_referee). This _must_ start
    # after sipp_referee - give it a few seconds to get the process off the
    # ground.
    from twisted.internet import reactor
    reactor.callLater(3, _start_referer_scenario, sipp_referer, test_object)

    return True
