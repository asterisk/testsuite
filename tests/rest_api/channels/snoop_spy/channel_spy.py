'''
Copyright (C) 2013, Digium, Inc.
Joshua Colp <jcolp@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging

LOGGER = logging.getLogger(__name__)


class Snoop(object):
    def __init__(self):
        self.bridge_id = None
        self.stops = 0


TEST = Snoop()


def on_start(ari, event, test_object):
    LOGGER.debug("on_start(%r)" % event)
    ari.post('channels', event['channel']['id'], 'snoop',
             spy='in', whisper='none', app='testsuite', appArgs='snoop')
    ari.post('channels', event['channel']['id'], 'play',
             media='sound:demo-congrats')
    return True


def on_snoop_start(ari, event, test_object):
    LOGGER.debug("on_snoop_start(%r)" % event)
    TEST.bridge_id = ari.post('bridges').json()['id']
    ari.post('bridges', TEST.bridge_id, 'addChannel',
             channel=event['channel']['id'])
    ari.post('channels', endpoint='Local/amd@default',
             app='testsuite', appArgs='amd')
    return True


def on_amd_start(ari, event, test_object):
    LOGGER.debug("on_amd_start(%r)" % event)
    ari.post('bridges', TEST.bridge_id, 'addChannel',
             channel=event['channel']['id'])
    return True


def on_end(ari, event, test_object):
    LOGGER.debug("on_end(%r)" % event)
    TEST.stops += 1
    if TEST.stops == 3:
        ari.delete('bridges', TEST.bridge_id)
    return True
