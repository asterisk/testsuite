'''
Copyright (C) 2013, Digium, Inc.
David M. Lee, II <dlee@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging

LOGGER = logging.getLogger(__name__)


class TestLogic(object):
    def __init__(self):
        self.channel_id = None
        self.bridge1_id = None
        self.bridge2_id = None


TEST = TestLogic()


def on_start(ari, event):
    LOGGER.debug("on_start(%r)" % event)
    TEST.channel_id = event['channel']['id']
    TEST.bridge1_id = ari.post('bridges').json()['id']
    TEST.bridge2_id = ari.post('bridges').json()['id']
    ari.post('channels', TEST.channel_id, 'answer')
    ari.post('bridges', TEST.bridge1_id, 'addChannel', channel=TEST.channel_id)
    return True


def on_enter(ari, event):
    channel_id = event['channel']['id']
    bridge_id = event['bridge']['id']
    assert TEST.channel_id == channel_id
    if TEST.bridge1_id == bridge_id:
        # Move to the next bridge
        ari.post('bridges', TEST.bridge2_id, 'addChannel',
                 channel=TEST.channel_id)
    elif TEST.bridge2_id == bridge_id:
        # Hangup
        ari.delete('channels', channel_id)
    else:
        assert False, "Unexpected bridge id %s" % bridge_id
    return True


def on_leave(ari, event):
    channel_id = event['channel']['id']
    bridge_id = event['bridge']['id']
    assert TEST.channel_id == channel_id
    assert TEST.bridge1_id == bridge_id or TEST.bridge2_id == bridge_id
    return True
