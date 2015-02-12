"""
Copyright (C) 2015, Digium, Inc.
Matt Jordan <mjordan@digium.com>
Joshua Colp <jcolp@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
import requests

LOGGER = logging.getLogger(__name__)

CHANNELS = []


def on_stasis_start(ari, event, test_object):
    """StasisStart event handler

    Keyword Arguments:
    event -- the ARI event. In this case, StasisStart.
    test_object -- our one and only test object
    """

    channel_id = event['channel']['id']
    CHANNELS.append(channel_id)

    if 'redirect_test' not in event.get('args'):
        ari.post('channels', endpoint='PJSIP/asterisk', app='testsuite',
                 appArgs='redirect_test')
        return True

    ari.set_allow_errors(True)

    def validate(expected, resp):
        """Validate a response against its expected code"""
        expected_code = requests.codes[expected]
        if expected_code != resp.status_code:
            test_object.set_passed(False)
            LOGGER.error("Expected %d (%s), got %s (%r)", expected_code,
                         expected, resp.status_code, resp.json())
            test_object.stop_reactor()

    LOGGER.debug('Verify no channel ID')
    resp = ari.post('channels', '', 'redirect', endpoint='PJSIP/asterisk')
    validate('bad_request', resp)

    LOGGER.debug('Verify invalid channel')
    resp = ari.post('channels', '12345', 'redirect', endpoint='PJSIP/asterisk')
    validate('not_found', resp)

    LOGGER.debug('Verify no endpoint')
    resp = ari.post('channels', channel_id, 'redirect')
    validate('bad_request', resp)

    LOGGER.debug('Verify invalid endpoint tech')
    resp = ari.post('channels', channel_id, 'redirect',
                    endpoint='Local/s@default')
    validate('unprocessable_entity', resp)

    LOGGER.debug('Verify no destination')
    resp = ari.post('channels', channel_id, 'redirect', endpoint='PJSIP/')
    validate('unprocessable_entity', resp)

    for channel in CHANNELS:
        ari.delete('channels', channel)

    test_object.stop_reactor()
    return True
