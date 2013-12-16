"""
Copyright (C) 2013, Digium, Inc.
David M. Lee, II <dlee@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging

LOGGER = logging.getLogger(__name__)

def eq(expected, actual):
    if expected != actual:
        LOGGER.error("Unexpected response '%s' != '%s'" % (expected, actual))
        raise ValueError("Test failed")

def get_vars(ari, channel_id):
    resp = ari.get('channels', channel_id, 'variable', variable='DP_SHELL')
    actual = resp.json()["value"]
    eq('works', actual)

    resp = ari.get('channels', channel_id, 'variable', variable='SHELL(echo -n fail)')
    actual = resp.json()["value"]
    eq('', actual)


def on_start(ari, event, test_object):
    LOGGER.debug("on_start(%r)" % event)
    channel_id = event["channel"]["id"]
    try:
        get_vars(ari, channel_id)
        return True
    finally:
        ari.delete('channels', channel_id)
