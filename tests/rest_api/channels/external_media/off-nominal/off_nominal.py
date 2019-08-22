'''
Copyright (C) 2019, Sangoma Technologies Corporation
George Joseph <gjoseph@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import json
import logging
from requests.exceptions import HTTPError
import requests

LOGGER = logging.getLogger(__name__)

def try_create(ari, channel_id, host, format, encapsulation, transport, resp_code):

    params = {
        'channelId': channel_id,
        'app': 'testsuite'
    }
    if host:
        params['external_host'] = host
    if format:
        params['format'] = format
    if encapsulation:
        params['encapsulation'] = encapsulation
    if transport:
        params['transport'] = transport

    try:
        resp = ari.post('channels', 'externalMedia', **params)
    except HTTPError as e:
        if e.response.status_code != resp_code:
            LOGGER.error("Unexpected response {0}".format(e.response))
            return False
        return True
    except:
        LOGGER.error("Unexpected exception when originating")
        return False
    else:
        if resp_code != 200:
            LOGGER.error("Originate succeeded when we expected failure")
            return False
        return True

def on_start(ari, event, obj):
    if event['args'] == ['FAIL']:
        LOGGER.error("Unexpected StasisStart on duplicate ID channel")
        return False

    passed = (
        try_create(ari, "test1", "127.0.0.1:59999", "ulaw", "rtp", "XXX", 501)     # bad transport
        and try_create(ari, "test2", "127.0.0.1:59999", "ulaw", "YYY", "udp", 501) # bad encapsulation
        and try_create(ari, "test3", "127.0.0.1:59999", "ulaw", "YYY", "XXX", 501) # both bad
        and try_create(ari, "test4", None, "ulaw", "rtp", "udp", 400)              # no host
        and try_create(ari, "test5", "127.0.0.1:59999", None, "rtp", "udp", 400)   # no format
        and try_create(ari, "test6", "127.0.0.1:59999", "XXX", "rtp", "udp", 400)  # bad format
        and try_create(ari, "test7", "127.0.0.1", "ulaw", "rtp", "udp", 400)       # bad host
        )
    ari.delete("channels", event['channel']['id'])
    return passed
