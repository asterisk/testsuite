'''
Copyright (C) 2013, Digium, Inc.
Joshua Colp <jcolp@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging

LOGGER = logging.getLogger(__name__)

CHANNELS = 0

def on_kickoff_start(ari, event, test_object):
    LOGGER.debug("on_kickoff_start(%r)" % event)
    for x in xrange(25):
        ari.post('channels', endpoint='Local/1000@default', app='testsuite', appArgs='blast')
    ari.delete('channels', event['channel']['id'])
    return True

def on_blast_start(ari, event, test_object):
    LOGGER.debug("on_blast_start(%r)" % event)
    return True

def on_channel_destroyed(ari, event, test_object):
	global CHANNELS
	LOGGER.debug("on_channel_destroyed: %s" % str(event.get('channel')))
	CHANNELS += 1
	if CHANNELS == 25:
		LOGGER.info("All channels destroyed")
		test_object.set_passed(True)
		test_object.stop_reactor()
	return True
