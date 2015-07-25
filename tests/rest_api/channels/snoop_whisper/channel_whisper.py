'''
Copyright (C) 2013, Digium, Inc.
Joshua Colp <jcolp@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging

LOGGER = logging.getLogger(__name__)


def on_start(ari, event, test_object):
    LOGGER.debug("on_start(%r)" % event)
    ari.post('channels', event['channel']['id'], 'snoop',
             spy='none', whisper='out', app='testsuite', appArgs='snoop')
    ari.post('channels', event['channel']['id'], 'play',
             media='sound:silence/10')
    return True


def on_snoop_start(ari, event, test_object):
    LOGGER.debug("on_snoop_start(%r)" % event)
    ari.post('channels', event['channel']['id'], 'play',
             media='sound:demo-congrats')
    return True
