'''
Copyright (C) 2014, Digium, Inc.
Joshua Colp <jcolp@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging
from sys import path

path.append("lib/python/asterisk")
from sipp import SIPpScenario

LOGGER = logging.getLogger(__name__)

class TestLogic(object):
    def __init__(self):
        self.originated_id = None
        self.bridge_id = None

TEST = TestLogic()

def on_kickoff_start(ari, event, test_object):
    LOGGER.debug("on_kickoff_start(%r)" % event)

    def _start_referer_scenario(referer_scenario, test_object):
        referer_scenario.run(test_object)

    sipp_referer = SIPpScenario(test_object.test_name,
        {'scenario':'referer.xml', '-p':'5065', '-3pcc':'127.0.0.1:5064'}, target='127.0.0.1')
    sipp_referee = SIPpScenario(test_object.test_name,
        {'scenario':'referee.xml', '-p':'5066', '-3pcc':'127.0.0.1:5064'}, target='127.0.0.1')

    sipp_referee.run(test_object)

    # The 3pcc scenario that first uses sendCmd (sipp_referer) will establish
    # a TCP socket with the other scenario (sipp_referee). This _must_ start
    # after sipp_referee - give it a few seconds to get the process off the
    # ground.
    from twisted.internet import reactor
    reactor.callLater(3, _start_referer_scenario, sipp_referer, test_object)

    TEST.bridge_id = ari.post('bridges').json()['id']
    TEST.originated_id = event['channel']['id']

    ari.post('bridges', TEST.bridge_id, 'addChannel', channel=event['channel']['id'])
    return True

def on_test_start(ari, event, test_object):
    LOGGER.debug("on_test_start(%r)" % event)

    ari.post('bridges', TEST.bridge_id, 'addChannel', channel=event['channel']['id'])
    return True

def on_attended_transfer(ari, event, test_object):
    LOGGER.debug("on_attended_transfer(%r)" % event)

    ari.delete('bridges', TEST.bridge_id)
    ari.delete('channels', TEST.originated_id)

    if not event['transferer_first_leg']['name'].startswith('PJSIP/bob-'):
        return False
    elif event['transferer_first_leg_bridge']['id'] != TEST.bridge_id:
        return False

    return True
