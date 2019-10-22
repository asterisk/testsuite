'''
Copyright (C) 2019, Sangoma Technologies Corporation
George Joseph <gjoseph@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import json
import requests

def on_start(ari, event, obj):
    params = {
        'channelId': 'testsuite-default-id',
        'external_host': '127.0.0.1:59999',
        'app': 'testsuite',
        'encapsulation': 'rtp',
        'transport': 'udp',
        'format': 'ulaw',
        'json': {'variables': {'CALLERID(name)': 'foo'}}
        }

    resp = ari.post('channels', 'externalMedia', **params)

    assert resp.json()['caller']['name'] == 'foo'
    assert resp.json()['channelvars']['UNICASTRTP_LOCAL_ADDRESS']
    assert resp.json()['channelvars']['UNICASTRTP_LOCAL_PORT']

    # Delete the channel we just created
    ari.delete('channels', resp.json()['id'])
    # Delete the implicit channel created by the test object
    ari.delete('channels', event['channel']['id'])

    return True
