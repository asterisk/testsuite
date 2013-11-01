'''
Copyright (C) 2013, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging

LOGGER = logging.getLogger(__name__)


class BridgeSimple(object):
    """
    Struct-like class to track the channel and bridge we care about
    """
    def __init__(self):
        self.channel_id = None
        self.bridge_id = None


TEST = BridgeSimple()


def on_start(ari, event):
    """
    Called when the channel enters the Stasis application. This function will
    create a bridge and add the channel to the bridge.
    """
    LOGGER.debug("on_start(%r)" % event)
    TEST.channel_id = event['channel']['id']
    TEST.bridge_id = ari.post('bridges').json()['id']
    ari.post('channels', TEST.channel_id, 'answer')
    ari.post('bridges', TEST.bridge_id, 'addChannel', channel=TEST.channel_id)
    return True


def on_enter(ari, event):
    """
    Called when the channel enters the bridge. This function will remove the
    bridge from the system.
    """
    channel_id = event['channel']['id']
    bridge_id = event['bridge']['id']
    assert TEST.channel_id == channel_id
    assert TEST.bridge_id == bridge_id
    ari.delete('bridges', bridge_id)
    return True


def on_destroy(ari, event):
    """
    Called when the bridge is destroyed. This function checks that the bridge
    no longer exists in the system but that the channel that was in the bridge
    still does exist.
    """
    bridge_id = event['bridge']['id']
    assert TEST.bridge_id == bridge_id
    result = True
    if not ari.get('channels', TEST.channel_id):
        LOGGER.error("Channel %s no longer exists after bridge deletion" %
                     TEST.channel_id)
        result = False
    if ari.get('bridges').json():
        LOGGER.error("Bridges exist on system after deletion")
        result = False
    ari.delete('channels', TEST.channel_id)
    return result
