'''
Copyright (C) 2016, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging
from requests.exceptions import HTTPError
import requests

LOGGER = logging.getLogger(__name__)

def try_originate(ari, channel_id, other_channel_id):
    try:
        ari.post('channels',
                 endpoint='Local/echo@default',
                 channelId=channel_id,
                 otherChannelId=other_channel_id,
                 app='testsuite',
                 appArgs='FAIL')
    except HTTPError as e:
        if e.response.status_code != 409:
            LOGGER.error("Unexpected response {0}".format(e.response))
            return False
        return True
    except:
        LOGGER.error("Unexpected exception when originating")
        return False
    else:
        LOGGER.error("Originate succeeded when we expected failure")
        return False


def try_originate_id(ari, channel_id, other_channel_id):
    try:
        ari.post('channels',
                 channel_id,
                 endpoint='Local/echo@default',
                 otherChannelId=other_channel_id,
                 app='testsuite',
                 appArgs='FAIL')
    except HTTPError as e:
        if e.response.status_code != 409:
            LOGGER.error("Unexpected response {0}".format(e.response))
            return False
        return True
    except:
        LOGGER.error("Unexpected exception when originating")
        return False
    else:
        LOGGER.error("Originate succeeded when we expected failure")
        return False


def on_start(ari, event, obj):
    if event['args'] == ['FAIL']:
        LOGGER.error("Unexpected StasisStart on duplicate ID channel")
        return False

    passed = (try_originate(ari, "eggs", "bacon") and
              try_originate(ari, "bacon", "eggs") and
              try_originate_id(ari, "eggs", "bacon") and
              try_originate_id(ari, "bacon", "eggs"))

    ari.delete("channels", event['channel']['id'])
    return passed
