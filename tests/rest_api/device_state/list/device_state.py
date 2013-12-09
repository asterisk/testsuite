'''
Copyright (C) 2013, Digium, Inc.
Kevin Harwell <kharwell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import requests

URL = 'deviceStates'
DEVICE1 = 'Stasis:Test1'
DEVICE2 = 'Stasis:Test2'
INITIAL_STATE = 'NOT_INUSE'

def on_start(ari, event, obj):
    ari.put(URL, DEVICE1, deviceState=INITIAL_STATE)
    ari.put(URL, DEVICE2, deviceState=INITIAL_STATE)

    devices = ari.get(URL).json()

    assert devices

    for device in devices:
        assert device['name'] == DEVICE1 or device['name'] == DEVICE2
        assert device['state'] == INITIAL_STATE

    ari.delete(URL, DEVICE1)
    ari.delete(URL, DEVICE2)
    ari.delete('channels', event['channel']['id'])
    return True
