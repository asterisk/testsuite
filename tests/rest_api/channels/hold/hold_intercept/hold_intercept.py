"""
Copyright (C) 2015, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging

LOGGER = logging.getLogger(__name__)

CHANNEL_ID = None


def on_start(ari, event, test_object):
    """StasisStart handler

    Keyword Arguments:
    ari         - ARI client object
    event       - StasisStart event data
    test_object - The one and only test object

    Returns:
    True if the event was handled successfully
    False if the event handling failed
    """
    global CHANNEL_ID
    LOGGER.debug("on_start({0})".format(event))

    CHANNEL_ID = event['channel']['id']

    ari.post('channels', CHANNEL_ID, 'variable',
             variable='HOLD_INTERCEPT(set)')

    ari.post('channels', CHANNEL_ID, 'hold')
    return True


def on_hold(ari, event, test_object):
    """ChannelHold handler

    Keyword Arguments:
    ari         - ARI client object
    event       - ChannelHold event data
    test_object - The one and only test object

    Returns:
    True if the event was handled successfully
    False if the event handling failed
    """
    LOGGER.debug("on_hold({0})".format(event))

    ari.delete('channels', CHANNEL_ID, 'hold')
    return True


def on_unhold(ari, event, test_object):
    """ChannelUnhold handler

    Keyword Arguments:
    ari         - ARI client object
    event       - ChannelUnhold event data
    test_object - The one and only test object

    Returns:
    True if the event was handled successfully
    False if the event handling failed
    """
    LOGGER.debug("on_unhold({0})".format(event))

    ari.delete('channels', CHANNEL_ID)
    return True
