'''
Copyright (C) 2013, Digium, Inc.
Kevin Harwell <kharwell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import requests

def on_start(ari, event, obj):
    channel_id = event['channel']['id']

    ari.post('channels', channel_id, 'record',
             name='test_adding_recording', format='wav')

    bridge_id = ari.post('bridges').json()['id']

    try:
        ari.post('bridges', bridge_id, 'addChannel', channel=channel_id)
    except requests.HTTPError, e:
        # assert '409' not in e
        assert 409 == e.response.status_code
    finally:
        # done so stop recording and remove
        ari.delete('recordings/live', 'test_adding_recording')
        ari.delete('channels', channel_id)

    return True
