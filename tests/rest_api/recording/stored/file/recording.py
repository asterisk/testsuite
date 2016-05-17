"""Check that we can retrieve the raw sound in a file

Copyright (C) 2016, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
import requests
import os

from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)

FILEPATH = '/tmp/superfly.wav'


def on_recording_finished(ari, event, test_object):
    LOGGER.info('Recording finished')

    url = ari.build_url('recordings/stored', 'superfly', 'file')
    resp = requests.get(url, stream=True, auth=ari.userpass)

    if resp.status_code != 200:
        LOGGER.error('Failed to download superfly: {0}'.format(
            resp.status_code))
        return False

    with open(FILEPATH, 'wb') as f:
        for chunk in resp:
            f.write(chunk)

    if (os.path.getsize(FILEPATH) == 0):
        LOGGER.error('Sound file superfly is 0 bytes')
        return False

    LOGGER.info('Superfly downloaded successfully')
    os.remove(FILEPATH)

    ari.delete('channels', 'testsuite-default-id')

    test_object.stop_reactor()

    return True
