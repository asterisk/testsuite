#!/usr/bin/env python
'''
Copyright (C) 2014, Digium, Inc.
John Bigelow <jbigelow@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging
import pjsua as pj

LOGGER = logging.getLogger(__name__)

class BobCallback(pj.BuddyCallback):
    """Derived class for buddy presence status changes."""

    def __init__(self, bob, test_object):
        """Constructor

        Keyword Arguments:
        bob The buddy object
        test_object The test object
        """
        pj.BuddyCallback.__init__(self, bob)
        self.bob = bob
        self.sub_cnt = 0
        self.test_object = test_object
        self.ami = self.test_object.ami[0]

    def on_state(self):
        info = self.buddy.info()

        LOGGER.info("Bob status to follow")
        LOGGER.info("Online status: %d" % info.online_status)
        LOGGER.info("Online text: %s" % info.online_text)
        LOGGER.info("Activity: %d" % info.activity)
        LOGGER.info("Sub state: %d" % info.sub_state)

        if info.online_status == 1 and info.sub_state == 4:
            LOGGER.info("Successfully subscribed.")
            self.sub_cnt += 1
            self.bob.unsubscribe()
        elif self.sub_cnt == 1:
            if info.online_status == 1 and info.sub_state == 5:
                LOGGER.info("Successfully un-subscribed.")
                self.test_object.set_passed(True)
                self.test_object.stop_reactor()
            else:
                LOGGER.info("Failed to un-subscribed.")
                self.test_object.set_passed(False)
                self.test_object.stop_reactor()


def buddy_subscribe(test_object, accounts):
    """The test's callback method.

    Keyword Arguments:
    test_object The test object
    accounts Configured accounts
    """
    alice = accounts.get('alice')
    bob = alice.buddies.get('bob')
    bob.set_callback(BobCallback(bob, test_object))
    bob.subscribe()

# vim:sw=4:ts=4:expandtab:textwidth=79
