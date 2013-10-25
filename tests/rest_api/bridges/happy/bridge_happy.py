'''
Copyright (C) 2013, Digium, Inc.
David M. Lee, II <dlee@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging

LOGGER = logging.getLogger(__name__)


class BridgeHappy(object):
    def __init__(self):
        self.channel_id = None
        self.bridge_id = None


TEST = BridgeHappy()


def on_start(ari, event, test_object):
    LOGGER.debug("on_start(%r)" % event)
    TEST.channel_id = event['channel']['id']
    TEST.bridge_id = ari.post('bridges').json()['id']
    ari.post('channels', TEST.channel_id, 'answer')
    ari.post('bridges', TEST.bridge_id, 'addChannel', channel=TEST.channel_id)
    return True


def on_enter(ari, event, test_object):
    channel_id = event['channel']['id']
    bridge_id = event['bridge']['id']
    assert TEST.channel_id == channel_id
    assert TEST.bridge_id == bridge_id
    ari.post('bridges', bridge_id, 'removeChannel', channel=channel_id)
    return True


def on_leave(ari, event, test_object):
    channel_id = event['channel']['id']
    bridge_id = event['bridge']['id']
    assert TEST.channel_id == channel_id
    assert TEST.bridge_id == bridge_id
    ari.delete('channels', channel_id)
    return True
