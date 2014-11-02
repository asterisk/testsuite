'''
Copyright (C) 2013, Digium, Inc.
David M. Lee, II <dlee@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging

logger = logging.getLogger(__name__)

id = None

STASIS_END_EVENTS = 0


def on_start(ari, event, test_object):
    logger.debug("on_start(%r)" % event)
    global id
    id = event['channel']['id']
    ari.post('channels', id, 'continue')
    return True


def on_end(ari, event, test_object):
    global id
    global STASIS_END_EVENTS

    logger.debug("on_end(%r)" % event)
    STASIS_END_EVENTS += 1
    if (STASIS_END_EVENTS == 2):
        test_object.stop_reactor()

    return id == event['channel']['id']


def on_second_start(ari, event, test_object):
    global id
    logger.debug("on_second_start(%r)" % event)
    ari.delete('channels', id)
    return id == event['channel']['id']
