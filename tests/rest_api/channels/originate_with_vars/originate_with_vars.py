'''
Copyright (C) 2013, Digium, Inc.
Kevin Harwell <kharwell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import json
import requests


def on_start(ari, event, obj):
    url = ari.build_url('channels')

    params = {
        'endpoint': 'Local/1000@default',
        'app': 'testsuite',
        'appArgs': 'with_vars'}

    data = {'variables': {'CALLERID(name)': 'foo'}}
    headers = {'Content-type': 'application/json'}

    resp = requests.post(url, params=params, data=json.dumps(data),
                         headers=headers, auth=ari.userpass)

    assert resp.json()['caller']['name'] == 'foo'
    ari.delete('channels', resp.json()['id'])

    ari.delete('channels', event['channel']['id'])
    return True
