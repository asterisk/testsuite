"""
Copyright (C) 2013, Digium, Inc.
David M. Lee, II <dlee@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging

LOGGER = logging.getLogger(__name__)

class TestData(object):
    def __init__(self):
        self.channel_id = None
        self.has_ended = False


TEST = TestData()


def on_start(ari, event, test_object):
    LOGGER.debug("on_start(%r)" % event)
    TEST.channel_id = event["channel"]["id"]
    ari.post("applications", "testsuite", "subscription",
             eventSource="channel:%s" % TEST.channel_id)
    ari.post("channels", TEST.channel_id, "continue")
    return True


def on_end(ari, event, test_object):
    LOGGER.debug("on_end(%r)" % event)
    TEST.has_ended = True
    return True


def on_state_change(ari, event, test_object):
    LOGGER.debug("on_state_change(%r)" % event)
    assert TEST.has_ended, "Expected no state changes before StasisEnd"
    test_object.stop_reactor()
    return True
