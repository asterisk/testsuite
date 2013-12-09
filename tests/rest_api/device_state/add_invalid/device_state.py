'''
Copyright (C) 2013, Digium, Inc.
Kevin Harwell <kharwell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import requests

URL = 'deviceStates'
INVALID_DEVICE = 'Invalid:Test'
MISSING_DEVICE = 'Stasis:'
INITIAL_STATE = 'NOT_INUSE'

def on_start(ari, event, obj):
    try:
        ari.put(URL, INVALID_DEVICE, deviceState=INITIAL_STATE)
    except requests.HTTPError, e:
        assert 409 == e.response.status_code

    try:
        ari.put(URL, MISSING_DEVICE, deviceState=INITIAL_STATE)
    except requests.HTTPError, e:
        assert 404 == e.response.status_code

    ari.delete('channels', event['channel']['id'])
    return True
