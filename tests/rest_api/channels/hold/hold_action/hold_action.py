'''
Copyright (C) 2015, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import uuid
import logging

LOGGER = logging.getLogger(__name__)


class TestTracker(object):
    """Object that keeps track of the test"""

    def __init__(self):
        self.channel_one = None
        self.channel_two = None
        self.bridge = None

TEST = TestTracker()


def on_first_start(ari, event, test_object):
    global TEST
    LOGGER.debug("on_start(%r)" % event)

    TEST.channel_one = event['channel']['id']

    second_channel_id = str(uuid.uuid4())
    ari.post('channels', second_channel_id, endpoint='Local/second@default',
             extension='echo', context='default', priority=1)

    return True


def on_second_start(ari, event, test_object):
    global TEST
    LOGGER.debug("on_start(%r)" % event)

    TEST.channel_two = event['channel']['id']

    TEST.bridge = ari.post('bridges', 'test-bridge',
                           type='mixing,dtmf_events').json()['id']

    ari.post('bridges', TEST.bridge, 'addChannel',
             channel='%s,%s' % (TEST.channel_one, TEST.channel_two))
    return True


def on_entered_bridge(ari, event, test_object):
    global TEST
    LOGGER.debug("on_entered_bridge(%r)" % event)

    bridge = event['bridge']
    if len(bridge['channels']) == 2:
        ari.post('channels', TEST.channel_one, 'hold')
    return True


def on_hold(ari, event, test_object):
    global TEST
    LOGGER.debug("on_hold(%r)" % event)

    ari.delete('channels', TEST.channel_one, 'hold')
    return True


def on_unhold(ari, event, test_object):
    global TEST
    LOGGER.debug("on_unhold(%r)" % event)

    ari.post('bridges', TEST.bridge, 'removeChannel', channel=TEST.channel_one)
    ari.post('bridges', TEST.bridge, 'removeChannel', channel=TEST.channel_two)

    test_object.set_passed(True)
    return True


def on_left_bridge(ari, event, test_object):
    global TEST
    LOGGER.debug('on_left_bridge(%r)' % event)

    bridge = event['bridge']
    if len(bridge['channels']) == 0:
        ari.delete('channels', TEST.channel_one)
        ari.delete('channels', TEST.channel_two)
        ari.delete('bridges', TEST.bridge)

    return True
