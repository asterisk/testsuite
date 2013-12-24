'''
Copyright (C) 2013, Digium, Inc.
Joshua Colp <jcolp@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging

LOGGER = logging.getLogger(__name__)

def on_kickoff_start(ari, event, test_object):
    LOGGER.debug("on_kickoff_start(%r)" % event)
    for x in xrange(50):
        ari.post('channels', endpoint='Local/1000@default', app='testsuite', appArgs='blast')
    ari.delete('channels', event['channel']['id'])
    return True

def on_blast_start(ari, event, test_object):
    LOGGER.debug("on_blast_start(%r)" % event)
    return True
