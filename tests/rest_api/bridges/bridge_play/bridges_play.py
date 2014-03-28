'''
Copyright (C) 2014, Digium, Inc.
Jonathan R. Rose <jrose@digium.com>

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


def on_start(ari, event, test_object):
    # When the channel enters stasis, create a bridge and add the channel.
    TEST.channel_id = event['channel']['id']
    TEST.bridge_id = ari.post('bridges').json()['id']

    ari.post('bridges', TEST.bridge_id, 'addChannel',
             channel=TEST.channel_id)

    return True


def on_enter_testsuite(ari, event, test_object):
    # When the channel enters the bridge, start the playback operation.
    assert TEST.bridge_id == event['bridge']['id']
    assert TEST.channel_id == event['channel']['id']

    # Start playback on the bridge
    ari.post('bridges', TEST.bridge_id, 'play',
             media='sound:tt-weasels')

    return True


def on_playback_finished(ari, event, test_object):
    # When the PlaybackFinished event is received, remove the channel.
    ari.post('bridges', TEST.bridge_id, 'removeChannel',
             channel=TEST.channel_id)

    return True


def on_channel_left_bridge(ari, event, test_object):
    # testsuite received a ChannelLeftBridge event, wrap the test up.
    assert TEST.bridge_id == event['bridge']['id']
    assert TEST.channel_id == event['channel']['id']

    ari.delete('channels', TEST.channel_id)
    ari.delete('bridges', TEST.bridge_id)

    return True
