'''
Copyright (C) 2014, Digium, Inc.
Joshua Colp <jcolp@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging
import subprocess

LOGGER = logging.getLogger(__name__)

class TestLogic(object):
    def __init__(self):
        self.channels = 0
        self.bridge_id = None
        self.originated_id = None
        self.pja = subprocess.Popen(['pjsua', '--local-port=5065', '--null-audio',
            '--id=sip:bob@127.0.0.1'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)

TEST = TestLogic()

def a_call_stasis():
    TEST.pja.stdin.write("m\n")
    TEST.pja.stdin.write("sip:stasis@127.0.0.1:5060\n")

def a_call_transfer():
    TEST.pja.stdin.write("x\n")
    TEST.pja.stdin.write("sip:1000@127.0.0.1:5060\n")

def on_kickoff_start(ari, event, test_object):
    LOGGER.debug("on_kickoff_start(%r)" % event)
    TEST.bridge_id = ari.post('bridges').json()['id']

    TEST.originated_id = event['channel']['id']
    ari.post('bridges', TEST.bridge_id, 'addChannel', channel=TEST.originated_id)

    a_call_stasis()
    return True

def on_test_start(ari, event, test_object):
    LOGGER.debug("on_test_start(%r)" % event)
    ari.post('bridges', TEST.bridge_id, 'addChannel', channel=event['channel']['id'])

    return True

def on_channel_entered_bridge(ari, event, test_object):

    TEST.channels += 1
    if TEST.channels == 1:
        a_call_transfer()

    return True

def on_replace_channel_enter(ari, event, test_object):
    ari.delete('channels', event['channel']['id'])
    ari.delete('channels', TEST.originated_id)
    ari.delete('bridges', TEST.bridge_id)
    return True

def on_blind_transfer(ari, event, test_object):
    LOGGER.debug("on_blind_transfer(%r)" % event)

    if event.get('result') != 'Success':
        LOGGER.error('Blind transfer failed: %s' % event.get('result'))
        return False

    # Transferer
    if not event['channel']['name'].startswith('PJSIP/bob-'):
        return False
    # Transferee
    elif event['transferee']['id'] != TEST.originated_id:
        return False
    # Channel replacing the transferer's channel
    elif not event['replace_channel']['name'].startswith('Local/1000@default-'):
        return False
    elif event['bridge']['id'] != TEST.bridge_id:
        return False

    return True

