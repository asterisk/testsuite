'''
Copyright (C) 2014, Digium, Inc.
Joshua Colp <jcolp@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging
import subprocess
import time

LOGGER = logging.getLogger(__name__)

class TestLogic(object):
	def __init__(self):
		self.channels = 0
		self.bridge_id = None
		self.pja = subprocess.Popen(['pjsua', '--local-port=5065', '--null-audio',
			'--id=sip:bob@127.0.0.1'],
			stdin=subprocess.PIPE, stdout=subprocess.PIPE)
		self.pjb = subprocess.Popen(['pjsua', '--local-port=5066', '--null-audio',
			'--id=sip:alice@127.0.0.1'],
			stdin=subprocess.PIPE, stdout=subprocess.PIPE)

TEST = TestLogic()

def a_call_stasis():
	TEST.pja.stdin.write("m\n")
	TEST.pja.stdin.write("sip:stasis@127.0.0.1:5060\n")

def b_call_stasis():
	TEST.pjb.stdin.write("m\n")
	TEST.pjb.stdin.write("sip:stasis@127.0.0.1:5060\n")

def on_third_leg(ami, event):
	TEST.pja.stdin.write("X\n")
	TEST.pja.stdin.write("1\n")
	return True

def a_call_app():
	TEST.pja.stdin.write("H\n")
	TEST.pja.stdin.write("m\n")
	TEST.pja.stdin.write("sip:1000@127.0.0.1:5060\n")

def on_kickoff_start(ari, event, test_object):
    LOGGER.debug("on_kickoff_start(%r)" % event)
    TEST.bridge_id = ari.post('bridges').json()['id']
    a_call_stasis()
    b_call_stasis()
    ari.delete('channels', event['channel']['id'])
    return True

def on_test_start(ari, event, test_object):
    LOGGER.debug("on_test_start(%r)" % event)
    ari.post('bridges', TEST.bridge_id, 'addChannel', channel=event['channel']['id'])

    TEST.channels += 1
    if TEST.channels == 2:
        a_call_app()

    return True

def on_attended_transfer(ari, event, test_object):
	LOGGER.debug("on_attended_transfer(%r)" % event)
	ari.delete('bridges', TEST.bridge_id)
	TEST.pjb.stdin.write("h\n")

	if not event['transferer_first_leg']['name'].startswith('PJSIP/bob-'):
		return False
	elif event['transferer_first_leg_bridge']['id'] != TEST.bridge_id:
		return False

	return True
