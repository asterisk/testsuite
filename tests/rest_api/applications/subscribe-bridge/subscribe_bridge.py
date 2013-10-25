'''
Copyright (C) 2013, Digium, Inc.
David M. Lee, II <dlee@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging

LOGGER = logging.getLogger(__name__)

class SubscribeBridge(object):
    def __init__(self):
        self.channels = None
        self.bridge_id = None


TEST = SubscribeBridge()


def on_start(ari, event):
    TEST.channel_id = event['channel']['id']
    TEST.bridge_id = ari.post('bridges').json()['id']
    ari.post('applications', 'bridge-watching-app', 'subscription',
             eventSource='bridge:%s' % TEST.bridge_id)
    ari.post('bridges', TEST.bridge_id, 'addChannel',
             channel=TEST.channel_id)
    return True


def on_enter_testsuite(ari, event):
    assert TEST.bridge_id == event['bridge']['id']
    assert TEST.channel_id == event['channel']['id']
    # Unsubscribe testsuite from the bridge
    ari.delete('applications', 'testsuite', 'subscription',
             eventSource='bridge:%s' % TEST.bridge_id)
    return True


def on_enter_watcher(ari, event):
    assert TEST.bridge_id == event['bridge']['id']
    assert TEST.channel_id == event['channel']['id']
    ari.post('bridges', TEST.bridge_id, 'removeChannel',
             channel=TEST.channel_id)
    return True


def on_channel_left_bridge(ari, event):
    assert TEST.bridge_id == event['bridge']['id']
    assert TEST.channel_id == event['channel']['id']
    ari.delete('channels', TEST.channel_id);
    return True
