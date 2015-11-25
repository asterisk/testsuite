"""
Copyright (C) 2015, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging

LOGGER = logging.getLogger(__name__)


class SubscribeTest(object):

    def __init__(self, module_config, test_object):
        """Constructor

        Keyword Arguments:
        test_object   The one and only test object
        module_config Our module config
        """
        self.test_object = test_object
        self.test_object.register_ami_observer(self.on_ami_connect)
        self.test_object.register_ws_event_handler(self.on_ws_event)
        self.events = {'BridgeDestroyed': 0,
                       'ChannelDestroyed': 0,
                       'DeviceStateChanged': 0}

    def on_ami_connect(self, ami):
        """AMI connect callback

        AMI connects after ARI, which should indicate that our test
        is ready to go.

        Keyword Arguments:
        ami The AMI instance
        """
        self.test_object.ari.post('channels',
            endpoint='Local/dial_alice@default', extension='echo')

    def on_ws_event(self, event):
        """ARI event callback

        Keyword Arguments:
        event The received ARI event
        """
        event_type = event.get('type')
        if event_type not in self.events:
            return
        self.events[event_type] += 1

        if (self.events['BridgeDestroyed'] == 1
            and self.events['ChannelDestroyed'] == 4
            and self.events['DeviceStateChanged'] == 8):

            LOGGER.info('All expected events received; stopping test')
            self.test_object.stop_reactor()
