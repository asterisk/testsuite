#!/usr/bin/env python

import sys
import logging
import pjsua as pj

sys.path.append("lib/python")

from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)

ALICE_RESULTS = [
    {'waiting': 'yes', 'msgs': '2/1'},
    {'waiting': 'yes', 'msgs': '5/4'},
]

BOB_RESULTS = [
    {'waiting': 'yes', 'msgs': '2/1'},
    {'waiting': 'yes', 'msgs': '3/3'},
]

class PJMWICallback(pj.AccountCallback):
    def __init__(self, account, results, controller):
        pj.AccountCallback.__init__(self, account)
        self.result_pos = 0
        self.results = results
        self.controller = controller
        self.checked_in = False

    def check_mwi(self, body):
        waiting = "Messages-Waiting: %s\r\n" % \
            self.results[self.result_pos]['waiting']

        msgs = "Voice-Message: %s (0/0)\r\n" % \
            self.results[self.result_pos]['msgs']

        if not waiting in body:
            LOGGER.error("Could not find pattern %s in MWI body %s" %
                         (waiting, body))
            controller.fail_test()
        if not msgs in body:
            LOGGER.error("Could not find pattern %s in MWI body %s" %
                         (msgs, body))
            controller.fail_test()
            self.test_object.set_passed(False)
            self.test_object.stop_reactor()

        self.result_pos += 1

    def on_mwi_info(self, body):
        self.check_mwi(body)
        self.controller.next_mwi(self)


class MWICallback(object):
    def __init__(self, test_object, accounts):
        self.mwis = [
            {'mailbox': 'mailbox_a', 'new': '2', 'old': '1'},
            {'mailbox': 'mailbox_b', 'new': '3', 'old': '3'},
        ]
        self.pos = 0
        self.ami = test_object.ami[0]
        self.test_object = test_object

        alice = accounts.get('alice')
        self.alice_cb = PJMWICallback(alice, ALICE_RESULTS, self)
        alice.account.set_callback(self.alice_cb)
        bob = accounts.get('bob')
        self.bob_cb = PJMWICallback(bob, BOB_RESULTS, self)
        bob.account.set_callback(self.bob_cb)

    def next_mwi(self, account):
        reactor.callFromThread(self._next_mwi_reactor, account);

    def _next_mwi_reactor(self, account):
        account.checked_in = True
        if self.alice_cb.checked_in and self.bob_cb.checked_in:
            self.send_mwi()

    def send_mwi(self):
        if self.pos >= len(self.mwis):
            self.test_object.set_passed(True)
            self.test_object.stop_reactor()
            return

        self.alice_cb.checked_in = False
        self.bob_cb.checked_in = False

        LOGGER.info("Sending MWI update. new: %s, old %s" %
                    (self.mwis[self.pos]['new'],
                     self.mwis[self.pos]['old']))
        message = {
            'Action': 'MWIUpdate',
            'Mailbox': self.mwis[self.pos]['mailbox'],
            'NewMessages': self.mwis[self.pos]['new'],
            'OldMessages': self.mwis[self.pos]['old']
        }
        self.pos += 1
        self.ami.sendMessage(message)

    def fail_test(self):
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()

def mwi_callback(test_object, accounts):
    cb = MWICallback(test_object, accounts)
    cb.send_mwi()
