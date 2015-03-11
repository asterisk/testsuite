'''
Copyright (C) 2013, Digium, Inc.
David M. Lee, II <dlee@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging
import requests

LOGGER = logging.getLogger(__name__)


class BridgeUnhappy(object):
    def __init__(self):
        self.ami_channel_id = None
        self.stasis_channel_id = None
        self.ami_ready = False
        self.stasis_ready = False
        self.has_run = False
        self.passing = False

    def on_start(self, ari, event):
        if not self.ami_channel_id:
            # Send the first channel out of Stasis
            self.ami_channel_id = event['channel']['id']
            ari.post('channels', self.ami_channel_id, 'answer')
            ari.post('channels', self.ami_channel_id, 'continue')
        elif not self.stasis_channel_id:
            self.stasis_channel_id = event['channel']['id']
            ari.post('channels', self.stasis_channel_id, 'answer')
            self.stasis_ready = True
        else:
            assert False, "Too many channels!"
        return True

    def on_end(self, ari, event):
        if event['channel']['id'] == self.ami_channel_id:
            self.ami_ready = True
        elif event['channel']['id'] != self.stasis_channel_id:
            assert False, "Unexpected channel %s leaving Stasis" % \
                event['channel']['id']

        return True

    def run_test(self, ari):
        if not (self.ami_ready and self.stasis_ready):
            # Not ready to run the test
            return

        if self.has_run:
            # only run once
            return

        try:
            self.passing = True
            self.__run_test(ari)
            assert self.passing
        finally:
            self.has_run = True
            ari.delete('channels', self.ami_channel_id)
            ari.delete('channels', self.stasis_channel_id)
            ari.set_allow_errors(False)

    def __run_test(self, ari):
        # Build some bridges to run the test with
        bridge_id = ari.post('bridges').json()['id']
        other_bridge_id = ari.post('bridges').json()['id']

        def validate(expected, resp):
            '''Validate a response against its expected code'''
            expected_code = requests.codes[expected]
            if expected_code != resp.status_code:
                self.passing = False
                LOGGER.error("Expected %d (%s), got %s (%r)", expected_code,
                             expected, resp.status_code, resp.json())
                raise ValueError("Test failed")

        # Disable auto-exceptions on HTTP errors.
        ari.set_allow_errors(True)

        #
        # Add to a nonexistent bridge
        #
        resp = ari.post('bridges', 'i-am-not-a-bridge', 'addChannel',
                        channel=self.stasis_channel_id)
        validate('not_found', resp)

        #
        # Remove from a nonexistent bridge
        #
        resp = ari.post('bridges', 'i-am-not-a-bridge', 'removeChannel',
                        channel=self.stasis_channel_id)
        validate('not_found', resp)

        #
        # Add a non-Stasis channel
        #
        resp = ari.post('bridges', bridge_id, 'addChannel',
                        channel=self.ami_channel_id)
        validate('unprocessable_entity', resp)

        #
        # Add a nonexistent channel
        #
        resp = ari.post('bridges', bridge_id, 'addChannel',
                        channel='i-am-not-a-channel')
        validate('bad_request', resp)

        #
        # Remove a nonexistent channel
        #
        resp = ari.post('bridges', bridge_id, 'removeChannel',
                        channel='i-am-not-a-channel')
        validate('bad_request', resp)

        #
        # Remove a channel that isn't in Stasis
        #
        resp = ari.post('bridges', bridge_id, 'removeChannel',
                        channel=self.ami_channel_id)
        validate('unprocessable_entity', resp)

        #
        # Remove a Stasis channel that isn't in a bridge at all
        #
        resp = ari.post('bridges', bridge_id, 'removeChannel',
                        channel=self.stasis_channel_id)
        validate('unprocessable_entity', resp)

        # We need a channel in a bridge for the next few tests
        resp = ari.post('bridges', bridge_id, 'addChannel',
                        channel=self.stasis_channel_id)
        resp.raise_for_status()

        #
        # Remove a channel from the wrong bridge
        #
        resp = ari.post('bridges', other_bridge_id, 'removeChannel',
                        channel=self.stasis_channel_id)
        validate('unprocessable_entity', resp)

        # And, just to be safe, make sure the channel is still in its bridge
        resp = ari.get('bridges', bridge_id)
        resp.raise_for_status()
        channels_in_bridge = resp.json()['channels']
        assert [self.stasis_channel_id] == channels_in_bridge

        # Okay, now remove it
        resp = ari.post('bridges', bridge_id, 'removeChannel',
                        channel=self.stasis_channel_id)
        resp.raise_for_status()
        ari.delete('bridges', bridge_id);
        ari.delete('bridges', other_bridge_id);


TEST = BridgeUnhappy()

END_EVENTS = 0


def on_start(ari, event, test_object):
    r = TEST.on_start(ari, event)
    if r:
        TEST.run_test(ari)
    return r


def on_end(ari, event, test_object):
    global END_EVENTS

    END_EVENTS += 1
    r = TEST.on_end(ari, event)
    if r:
        TEST.run_test(ari)
    if END_EVENTS == 2:
        test_object.stop_reactor()
    return r
