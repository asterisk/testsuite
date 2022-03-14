#!/usr/bin/env python
"""Pluggable modules for the mwi_aggregate test

Copyright (C) 2014, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging

sys.path.append("lib/python")
from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)

mwis = [
    {'mailbox': 'mailbox_a', 'new': '2', 'old': '1'},
    {'mailbox': 'mailbox_b', 'new': '3', 'old': '3'},
]

def walk_states(test_object, accounts):

    testami = test_object.ami[0]
    statedelay = 2
    for mwi in mwis:
        LOGGER.info("Sending MWI update. new: %s, old %s" %
                    (mwi['new'],
                     mwi['old']))
        message = {
            'Action': 'MWIUpdate',
            'Mailbox': mwi['mailbox'],
            'NewMessages': mwi['new'],
            'OldMessages': mwi['old']
        }
        reactor.callLater(statedelay, testami.sendMessage, message)
        statedelay += 1
