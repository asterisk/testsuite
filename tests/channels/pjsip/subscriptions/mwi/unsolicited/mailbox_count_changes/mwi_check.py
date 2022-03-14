#!/usr/bin/env python

import sys
import logging

sys.path.append("lib/python")

from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)

mwis = [
        {'new': '2', 'old': '0'},
        {'new': '1', 'old': '1'},
        {'new': '0', 'old': '2'},
]

def walk_states(test_object, junk):

    testami = test_object.ami[0]
    statedelay = 2
    for mwi in mwis:
        LOGGER.info("Sending MWI update. new: %s, old %s" %
                    (mwi['new'],
                     mwi['old']))
        message = {
            'Action': 'MWIUpdate',
            'Mailbox': 'alice',
            'NewMessages': mwi['new'],
            'OldMessages': mwi['old']
        }
        reactor.callLater(statedelay, testami.sendMessage, message)
        statedelay += .25

    # delete mailbox after walking states
    LOGGER.info("Deleting Mailbox")
    message = {
            'Action': 'MWIDelete',
            'Mailbox': 'alice',
        }
    reactor.callLater(statedelay, testami.sendMessage, message)
