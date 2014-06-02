#!/usr/bin/env python
'''
Copyright (C) 2014, Digium, Inc.
John Bigelow <jbigelow@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging
import pjsua as pj
from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)
URI = ["sip:bob@127.0.0.1", "sip:bob_two@127.0.0.1", "sip:charlie@127.0.0.1"]
ITERATION = 0

class CharlieCallback(pj.AccountCallback):
    """Derived callback class for Charlie's account."""

    def __init__(self, controller, account=None):
        pj.AccountCallback.__init__(self, account)
        self.controller = controller
        self.charlie_call = None

    def on_incoming_call2(self, call, msg):
        self.charlie_call = call
        LOGGER.info("Incoming call for Charlie '%s' from '%s'." %
                (call.info().uri, call.info().remote_uri))
        if ITERATION > 0:
            referred_by_hdr = "Referred-By: <sip:bob@127.0.0.1;ob>"
            if (referred_by_hdr not in msg.msg_info_buffer):
                LOGGER.warn("Expected header not found: '%s'" % referred_by_hdr)
                self.controller.test_object.set_passed(False)
                self.controller.test_object.stop_reactor()

        inbound_cb = CharliePhoneCallCallback(call)
        call.set_callback(inbound_cb)
        call.answer(200)
        reactor.callLater(1, self.hangup_call)

    def hangup_call(self):
        """Hang up the call."""
        LOGGER.info("Hanging up Charlie")
        self.charlie_call.hangup(code=200, reason="Q.850;cause=16")

class BobCallback(pj.AccountCallback):
    """Derived callback class for Bob's account."""

    def __init__(self, account=None):
        pj.AccountCallback.__init__(self, account)
        self.bob_call = None

    def on_incoming_call(self, call):
        self.bob_call = call
        LOGGER.info("Incoming call for Bob '%s' from '%s'." %
                (call.info().uri, call.info().remote_uri))
        inbound_cb = BobPhoneCallCallback(call)
        call.set_callback(inbound_cb)
        call.answer(200)

class AlicePhoneCallCallback(pj.CallCallback):
    """Derived callback class for Alice's call."""

    def __init__(self, call=None):
        pj.CallCallback.__init__(self, call)

    def on_state(self):
        log_call_info(self.call.info())
        if self.call.info().state == pj.CallState.DISCONNECTED:
            LOGGER.info("Call disconnected: '%s'" % self.call)

class BobPhoneCallCallback(pj.CallCallback):
    """Derived callback class for Bob's call."""

    def __init__(self, call=None):
        pj.CallCallback.__init__(self, call)

    def on_state(self):
        log_call_info(self.call.info())
        if self.call.info().state == pj.CallState.CONFIRMED:
            LOGGER.info("Call is up between Alice and Bob. Transferring call" \
                    " to Charlie.")
            self.transfer_call()
        if self.call.info().state == pj.CallState.DISCONNECTED:
            LOGGER.info("Call disconnected: '%s'" % self.call)

    def transfer_call(self):
        """Transfer the call."""
        try:
            LOGGER.info("Attempting to blind transfer the call.")
            self.call.transfer(URI[2])
            LOGGER.info("The call is %s" % self.call)
        except:
            LOGGER.warn("Failed to transfer the call! Retrying...")
            reactor.callLater(.2, self.transfer_call)

    def on_transfer_status(self, code, reason, final, cont):
        log_call_info(self.call.info())
        if code == 200 and reason == "OK" and final == 1 and cont == 0:
            LOGGER.info("Transfer target answered the call.")
            LOGGER.debug("Call uri: '%s'; remote uri: '%s'" %
                    (self.call.info().uri, self.call.info().remote_uri))
            LOGGER.info("Hanging up Bob")
            self.call.hangup(code=200, reason="Q.850;cause=16")
        return cont

class CharliePhoneCallCallback(pj.CallCallback):
    """Derived callback class for Charlie's call."""

    def __init__(self, call=None):
        pj.CallCallback.__init__(self, call)

    def on_state(self):
        log_call_info(self.call.info())
        if self.call.info().state == pj.CallState.DISCONNECTED:
            LOGGER.info("Call disconnected: '%s'" % self.call)

class AMICallback(object):
    """Class to set up callbacks and place calls."""

    def __init__(self, test_object, accounts):
        self.test_object = test_object
        self.ami = self.test_object.ami[0]
        self.ami.registerEvent('Hangup', self.hangup_event_handler)
        self.alice = accounts.get('alice')
        bob = accounts.get('bob')
        charlie = accounts.get('charlie')
        self.bob_cb = BobCallback()
        self.charlie_cb = CharlieCallback(self)
        bob.account.set_callback(self.bob_cb)
        charlie.account.set_callback(self.charlie_cb)
        self.channels_hungup = 0

    def hangup_event_handler(self, ami, event):
        """AMI hang up event callback."""
        global ITERATION
        LOGGER.debug("Hangup detected for channel '%s'" % event['channel'])
        self.channels_hungup += 1
        if self.channels_hungup == 3 and ITERATION == 0:
            LOGGER.info("Starting second iteration.")
            self.channels_hungup = 0
            ITERATION += 1
            lock = self.alice.pj_lib.auto_lock()
            self.make_call(self.alice.account, URI[1])
            del lock
        elif self.channels_hungup == 3 and ITERATION == 1:
            self.test_object.stop_reactor()

    def make_call(self, acc, uri):
        """Place a call.

        Keyword Arguments:
        acc The pjsua to make the call from
        uri The URI to dial
        """
        try:
            LOGGER.info("Making call to '%s'" % uri)
            acc.make_call(uri, cb=AlicePhoneCallCallback())
        except pj.Error, err:
            LOGGER.error("Exception: %s" % str(err))


def log_call_info(call_info):
    """Log call info."""
    LOGGER.debug("Call '%s' <-> '%s'" % (call_info.uri, call_info.remote_uri))
    LOGGER.debug("Call state: '%s'; last code: '%s'; last reason: '%s'" %
            (call_info.state_text, call_info.last_code, call_info.last_reason))

def transfer(test_object, accounts):
    """The test's callback method.

    Keyword Arguments:
    test_object The test object
    accounts Configured accounts
    """
    LOGGER.info("Starting first iteration.")
    alice = accounts.get('alice')
    obj = AMICallback(test_object, accounts)
    lock = alice.pj_lib.auto_lock()
    obj.make_call(accounts['alice'].account, URI[0])
    del lock


# vim:sw=4:ts=4:expandtab:textwidth=79
