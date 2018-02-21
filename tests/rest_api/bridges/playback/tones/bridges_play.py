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
        self.channel_id = None

BRIDGE_ID = 'test-tones-bridge'
TEST = SubscribeBridge()


def on_start(ari, event, test_object):
    """ When the channel enters stasis, create a bridge and add the channel. """
    TEST.channel_id = event['channel']['id']

    ari.post('bridges',
             bridgeId=BRIDGE_ID)

    ari.post('bridges', BRIDGE_ID, 'addChannel',
             channel=TEST.channel_id)

    return True


def on_playback_finished(ari, event, test_object):
    """ When the PlaybackFinished event is received, remove the channel. """
    ari.post('bridges', BRIDGE_ID, 'removeChannel',
             channel=TEST.channel_id)

    return True


def on_channel_left_bridge(ari, event, test_object):
    """ testsuite received a ChannelLeftBridge event, wrap the test up. """
    assert BRIDGE_ID == event['bridge']['id']
    assert TEST.channel_id == event['channel']['id']

    ari.delete('channels', TEST.channel_id)
    ari.delete('bridges', BRIDGE_ID)

    return True
