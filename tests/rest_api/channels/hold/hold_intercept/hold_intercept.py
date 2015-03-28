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
    global CHANNEL_ID
    LOGGER.debug("on_start(%r)" % event)

    CHANNEL_ID = event['channel']['id']

    ari.post('channels', CHANNEL_ID, 'variable',
             variable='HOLD_INTERCEPT(set)')

    ari.post('channels', CHANNEL_ID, 'hold')
    return True


def on_hold(ari, event, test_object):
    LOGGER.debug("on_hold(%r)" % event)

    ari.delete('channels', CHANNEL_ID, 'hold')
    return True


def on_unhold(ari, event, test_object):
    LOGGER.debug("on_unhold(%r)" % event)

    ari.delete('channels', CHANNEL_ID)
    return True
