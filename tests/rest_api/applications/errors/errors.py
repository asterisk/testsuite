'''
Copyright (C) 2013, Digium, Inc.
David M. Lee, II <dlee@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import requests
import logging

LOGGER = logging.getLogger(__name__)


def validate(expected, resp):
    '''Validate a response against its expected code'''
    expected_code = requests.codes[expected]
    if expected_code != resp.status_code:
        LOGGER.error("%s: Expected %d (%s), got %s (%r)", resp.url,
                     expected_code, expected, resp.status_code, resp.json())
        raise ValueError('Test failed')


def on_start(ari, event, test_object):
    LOGGER.debug('on_start(%r)' % event)

    channel_id = event["channel"]["id"]

    app_list = ari.get('applications').json()
    assert 1 == len(app_list)
    assert 'testsuite' == app_list[0].get('name')


    ari.set_allow_errors(True)

    resp = ari.get('applications', 'notanapp')
    validate('not_found', resp)

    resp = ari.post('applications', 'testsuite', 'subscription')
    validate('bad_request', resp)

    resp = ari.delete('applications', 'testsuite', 'subscription')
    validate('bad_request', resp)

    resp = ari.post('applications', 'testsuite', 'subscription',
             eventSource='notascheme:foo')
    validate('bad_request', resp)

    resp = ari.delete('applications', 'testsuite', 'subscription',
             eventSource='notascheme:foo')
    validate('bad_request', resp)

    resp = ari.post('applications', 'testsuite', 'subscription',
             eventSource='channel:notachannel')
    validate('unprocessable_entity', resp)

    resp = ari.delete('applications', 'testsuite', 'subscription',
             eventSource='channel:notachannel')
    validate('unprocessable_entity', resp)

    ari.post('channels', channel_id, 'continue')
    return True
