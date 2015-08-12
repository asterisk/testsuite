#!/usr/bin/env python

import sys
import logging
import pjsua as pj

sys.path.append("lib/python")

from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)


class AliceCallback(pj.AccountCallback):
    mwis = [
        {'new': '2', 'old': '0'},
        {'new': '1', 'old': '1'},
        {'new': '0', 'old': '2'},
    ]
    results = [
        {'waiting': 'yes', 'msgs': '2/0'},
        {'waiting': 'yes', 'msgs': '1/1'},
        {'waiting': 'no', 'msgs': '0/2'},
        {'waiting': 'no', 'msgs': '0/0'},
    ]

    def __init__(self, alice, test_object):
        pj.AccountCallback.__init__(self, alice)
        self.pos = 0
        self.result_pos = 0
        self.test_object = test_object
        self.ami = self.test_object.ami[0]
        self.deleted = False

    def check_mwi(self, body):
        waiting = "Messages-Waiting: %s\r\n" % \
            self.results[self.result_pos]['waiting']

        msgs = "Voice-Message: %s (0/0)\r\n" % \
            self.results[self.result_pos]['msgs']

        if not waiting in body:
            # On the first MWI NOTIFY it is possible for the contents to not be
            # what we expect as Asterisk will send an initial NOTIFY on REGISTER.
            # Since we attach our MWI callback after the registration has started
            # we may or may not even get the NOTIFY (depending on timing).
            # Due to this we don't treat the match failure as fatal when expecting
            # the first result. If it is indeed incorrect then either the next
            # NOTIFY will also fail to match or the reactor will time out.
            if self.result_pos == 0:
                LOGGER.info("Could not find pattern %s in MWI body %s but treating as initial" %
                    (waiting, body))
                return

            LOGGER.error("Could not find pattern %s in MWI body %s" %
                         (waiting, body))
            self.test_object.set_passed(False)
            self.test_object.stop_reactor()
        if not msgs in body:
            if self.result_pos == 0:
                LOGGER.info("Could not find pattern %s in MWI body %s but treating as initial" %
                    (msgs, body))
            return

            LOGGER.error("Could not find pattern %s in MWI body %s" %
                         (msgs, body))
            self.test_object.set_passed(False)
            self.test_object.stop_reactor()

        self.result_pos += 1

    def on_mwi_info(self, body):
        self.check_mwi(body)
        self.pos += 1
        if (self.pos < len(self.mwis)):
            self.send_mwi()
            return

        if (self.deleted):
            self.test_object.set_passed(True)
            self.test_object.stop_reactor()
        else:
            self.delete_mwi()
            self.deleted = True

    def send_mwi(self):
        LOGGER.info("Sending MWI update. new: %s, old %s" %
                    (self.mwis[self.pos]['new'],
                     self.mwis[self.pos]['old']))
        message = {
            'Action': 'MWIUpdate',
            'Mailbox': 'alice',
            'NewMessages': self.mwis[self.pos]['new'],
            'OldMessages': self.mwis[self.pos]['old']
        }
        reactor.callFromThread(self.ami.sendMessage, message)

    def delete_mwi(self):
        LOGGER.info("Deleting Mailbox")
        message = {
            'Action': 'MWIDelete',
            'Mailbox': 'alice',
        }
        reactor.callFromThread(self.ami.sendMessage, message)


def mwi_callback(test_object, accounts):
    alice = accounts.get('alice')
    cb = AliceCallback(alice, test_object)
    alice.account.set_callback(cb)
    cb.send_mwi()
