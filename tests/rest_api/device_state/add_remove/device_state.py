'''
Copyright (C) 2013, Digium, Inc.
Kevin Harwell <kharwell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import requests

URL = 'deviceStates'
DEVICE = 'Stasis:Test'
INITIAL_STATE = 'NOT_INUSE'


def on_start(ari, event, obj):
    ari.put(URL, DEVICE, deviceState=INITIAL_STATE)
    assert ari.get(URL, DEVICE).json()['state'] == INITIAL_STATE

    ari.delete(URL, DEVICE)
    assert ari.get(URL, DEVICE).json()['state'] == 'UNKNOWN'

    ari.delete('channels', event['channel']['id'])
    return True
