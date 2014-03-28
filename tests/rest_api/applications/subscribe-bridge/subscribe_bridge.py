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

def on_start(ari, event, test_object):
    TEST.channel_id = event['channel']['id']
    TEST.bridge_id = ari.post('bridges').json()['id']

    # at this point the 'testsuite' app is subscribed to the bridge
    # subscribe another app 'bridge-watching-app' to receive events
    ari.post('applications', 'bridge-watching-app', 'subscription',
             eventSource='bridge:%s' % TEST.bridge_id)

    # both applications should receive a ChannelEnteredBridge
    # event upon adding a channel
    ari.post('bridges', TEST.bridge_id, 'addChannel',
             channel=TEST.channel_id)
    return True

def on_enter_testsuite(ari, event, test_object):
    # the testsuite application received a ChannelEnteredBridge event
    assert TEST.bridge_id == event['bridge']['id']
    assert TEST.channel_id == event['channel']['id']

    # now unsubscribe testsuite from the bridge-watching-app
    ari.delete('applications', 'bridge-watching-app', 'subscription',
             eventSource='bridge:%s' % TEST.bridge_id)

    # upon removing the channel testsuite should receive no event, but
    # the still subscribed bridge-watching-app should
    ari.post('bridges', TEST.bridge_id, 'removeChannel',
             channel=TEST.channel_id)
    return True

def on_channel_left_bridge(ari, event, test_object):
    # bridge-watching-app received a ChannelLeftBridge event
    assert TEST.bridge_id == event['bridge']['id']
    assert TEST.channel_id == event['channel']['id']
    ari.delete('channels', TEST.channel_id);
    return True
