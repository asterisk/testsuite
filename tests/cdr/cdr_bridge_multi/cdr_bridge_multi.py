"""
Test CDRs in a multi-party bridge

Copyright (C) 2014, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
import re

LOGGER = logging.getLogger(__name__)

TEST_STATE = None

# Yay for human sorting:
# http://stackoverflow.com/questions/5967500/how-to-correctly-sort-a-string-with-a-number-inside
def atoi(text):
    return int(text) if text.isdigit() else text

def natural_keys(text):
    return [atoi(c) for c in re.split('(\d+)', text)]

class TestState(object):
    """Base class for the states the test transitions through"""

    def __init__(self, next_state=None):
        """Constructor

        Keyword Arguments:
        next_state Class that we should transition to next
        """
        self.next_state = next_state
        self.ari = None

    def _set_ari(self, ari):
        """Set the ARI object on ourselves"""
        if not self.ari:
            self.ari = ari

    def handle_start(self, ari, event, test_object):
        """Handle a StasisStart event

        Keyword Arguments:
        ari         Our ARI connection back to Asterisk
        event       The StasisStart event
        test_obejct The one and only test object
        """
        self._set_ari(ari)
        return

    def handle_enter(self, ari, event, test_object):
        """Handle a ChannelEnteredBridge event

        Keyword Arguments:
        ari         Our ARI connection back to Asterisk
        event       The ChannelEnteredBridge event
        test_obejct The one and only test object
        """
        self._set_ari(ari)
        return

    def handle_leave(self, ari, event, test_object):
        """Handle a ChannelLeftBridge event

        Keyword Arguments:
        ari         Our ARI connection back to Asterisk
        event       The ChannelLeftBridge event
        test_obejct The one and only test object
        """
        self._set_ari(ari)
        return

    def change_state(self, test_object):
        """Change the test state to the next object

        A concrete implementation should call this when done.
        This will transition to the next state, or end the test
        """
        if not self.next_state:
            test_object.stop_reactor()
        else:
            global TEST_STATE
            TEST_STATE = self.next_state(ari=self.ari)

class ChannelStartState(TestState):
    """State that manages getting the channels into the bridge.

    Once all channels are in the bridge, it hands control over
    to ChannelsInBridge
    """

    def __init__(self):
        """Constructor"""
        super(ChannelStartState, self).__init__(ChannelsInBridge)
        LOGGER.debug('Test in ChannelStartState')

        self.channels = []
        self.channels_entered = 0

    def handle_start(self, ari, event, test_object):
        """Handler for StasisStart"""
        super(ChannelStartState, self).handle_start(ari, event, test_object)

        self.channels.append(event['channel']['id'])
        if len(self.channels) < 5:
            return

        self.channels.sort(key=natural_keys)

        # Make the bridge and put our channels into it. Note that we place
        # the channels into the bridge in a somewhat haphazard order for "fun",
        # if we don't make pairings correctly even when channels enter the bridge
        # in a goofy way, our CDRs will be wrong!
        ari.post('bridges', bridgeId='cdr_bridge')
        for ind in [0, 2, 4, 3, 1]:
            LOGGER.debug('Adding channel %s to bridge' % self.channels[ind])
            ari.post('bridges', 'cdr_bridge', 'addChannel', channel=self.channels[ind])

    def handle_enter(self, ari, event, test_object):
        """Handler for ChannelEnteredBridge"""
        super(ChannelStartState, self).handle_enter(ari, event, test_object)
        self.channels_entered += 1
        if (self.channels_entered == 5):
            self.change_state(test_object)

class ChannelsInBridge(TestState):
    """State that handles once all the channels are in the bridge.

    This state removes channel 0 and channel 3. Once removed, it
    puts them back in. Once back in, it transitions to the next
    state, ChannelsLeaveBridge
    """

    def __init__(self, ari):
        """Constructor"""
        super(ChannelsInBridge, self).__init__(ChannelsLeaveBridge)
        LOGGER.debug('Test in ChannelsInBridge')

        self.ari = ari
        self.channels_left = 0
        self.channels_entered = 0
        self.channels = self.ari.get('bridges', 'cdr_bridge').json().get('channels')
        self.channels.sort(key=natural_keys)

        LOGGER.debug('Removing channels %s and %s from bridge' % (self.channels[0], self.channels[3]))
        self.ari.post('bridges', 'cdr_bridge', 'removeChannel', channel=self.channels[0])
        self.ari.post('bridges', 'cdr_bridge', 'removeChannel', channel=self.channels[3])

    def handle_leave(self, ari, event, test_object):
        """Handler for ChannelLeftBridge"""
        super(ChannelsInBridge, self).handle_leave(ari, event, test_object)

        self.channels_left += 1
        if (self.channels_left == 2):
            LOGGER.debug('Adding channels %s and %s to bridge' % (self.channels[3], self.channels[0]))
            self.ari.post('bridges', 'cdr_bridge', 'addChannel', channel=self.channels[3])
            self.ari.post('bridges', 'cdr_bridge', 'addChannel', channel=self.channels[0])

    def handle_enter(self, ari, event, test_object):
        """Handler for ChannelEnteredBridge"""
        super(ChannelsInBridge, self).handle_enter(ari, event, test_object)
        self.channels_entered += 1
        if (self.channels_entered == 2):
            self.change_state(test_object)

class ChannelsLeaveBridge(TestState):
    """State that handles all channels leaving the bridge

    This state boots everyone out of the bridge. Once all are
    out, it hangs them up in order and deletes the bridge. It
    the ends the test by transitioning to the next state (None)
    """

    def __init__(self, ari):
        """Constructor"""
        super(ChannelsLeaveBridge, self).__init__(None)
        LOGGER.debug('Test in ChannelsLeaveBridge')

        self.ari = ari
        self.channels = self.ari.get('bridges', 'cdr_bridge').json().get('channels')
        self.channels.sort(key=natural_keys)
        self.left_channels = 0

        for channel in self.channels:
            LOGGER.debug('Removing channel %s from bridge' % channel)
            self.ari.post('bridges', 'cdr_bridge', 'removeChannel', channel=channel)

    def handle_leave(self, ari, event, test_object):
        """Handler for ChannelLeftBridge"""
        super(ChannelsLeaveBridge, self).handle_leave(ari, event, test_object)

        self.left_channels += 1
        if (self.left_channels) == 5:
            for chan in self.channels:
                LOGGER.debug('Hanging up channel %s' % chan)
                ari.delete('channels', chan)
            ari.delete('bridges', 'cdr_bridge')
            self.change_state(test_object)

TEST_STATE = ChannelStartState()

def on_start(ari, event, test_object):
    """Handle the StasisStart event"""
    TEST_STATE.handle_start(ari, event, test_object)
    return True

def on_enter(ari, event, test_object):
    """Handle the ChannelEnteredBridge event"""
    TEST_STATE.handle_enter(ari, event, test_object)
    return True

def on_leave(ari, event, test_object):
    """Handle the ChannelLeftBridge event"""
    TEST_STATE.handle_leave(ari, event, test_object)
    return True

