#!/usr/bin/env python
"""Pluggable module and callback methods.

Note: Nothing here sets a pass/fail result.

Copyright (C) 2014, Digium, Inc.
John Bigelow <jbigelow@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import os
import logging
import pjsua as pj
from twisted.internet import reactor

sys.path.append("lib/python/asterisk")
import pjsua_mod

LOGGER = logging.getLogger(__name__)
THIS_FILE = os.path.basename(__file__)
URI = None
PJSUA_ACCOUNTS = None


class InitMod(object):
    """Pluggable module class to override & extend pjsua_mod.PJsua YAML config

    This provides the ability to configure SIP URI's within YAML configuration
    files for dialing from PJSUA accounts. It also overrides the
    callback_module & callback_method YAML config options pointing them to this
    module and the 'pjsua_initialized' method for when all endpoints have
    registered.
    """

    def __init__(self, instance_config, test_object):
        """Constructor"""
        global URI
        instance_config['callback_module'] = os.path.splitext(THIS_FILE)[0]
        instance_config['callback_method'] = 'pjsua_initialized'
        pjsua_mod.PJsua(instance_config, test_object)
        self.test_object = test_object
        self.config = instance_config
        URI = {}
        for account in self.config['accounts']:
            if 'call_uri' not in account and 'transfer_uri' not in account:
                continue
            URI[account['name']] = {}
            if account.get('call_uri') is not None:
                URI[account['name']]['call_uri'] = account.get('call_uri')
            if account.get('transfer_uri') is not None:
                URI[account['name']]['transfer_uri'] = \
                    account.get('transfer_uri')
        LOGGER.info("Pluggable module initialized.")


class AlicePhoneCallCallback(pj.CallCallback):
    """Derived callback class for Alice's call."""

    def __init__(self, call=None):
        pj.CallCallback.__init__(self, call)

    def on_state(self):
        """Callback for call state changes."""
        log_call_info(self.call.info())
        if self.call.info().state == pj.CallState.CONFIRMED:
            LOGGER.info("Call is up: '%s'" % self.call)
        if self.call.info().state == pj.CallState.DISCONNECTED:
            LOGGER.info("Call disconnected: '%s'" % self.call)

    def transfer_call(self):
        """Transfer the call."""
        try:
            LOGGER.info("'%s' is blind transfering the call to '%s'." %
                        (self.call.info().uri, URI['alice']['transfer_uri']))
            self.call.transfer(URI['alice']['transfer_uri'])
        except:
            LOGGER.warn("Failed to transfer the call! Retrying...")
            reactor.callLater(.2, self.transfer_call)

    def on_transfer_status(self, code, reason, final, cont):
        """Callback for the status of a previous call transfer request."""
        log_call_info(self.call.info())
        if code == 200 and reason == "OK" and final == 1 and cont == 0:
            LOGGER.info("Transfer target answered the call.")
            LOGGER.debug("Call uri: '%s'; remote uri: '%s'" %
                         (self.call.info().uri,
                          self.call.info().remote_uri))
            LOGGER.info("Hanging up Alice")
            self.call.hangup(code=200, reason="Q.850;cause=16")
        return cont


class BobPhoneCallCallback(pj.CallCallback):
    """Derived callback class for Bob's call."""

    def __init__(self, call=None):
        pj.CallCallback.__init__(self, call)

    def on_state(self):
        """Callback for call state changes."""
        log_call_info(self.call.info())
        if self.call.info().state == pj.CallState.DISCONNECTED:
            LOGGER.info("Call disconnected: '%s'" % self.call)
        if self.call.info().state == pj.CallState.DISCONNECTED:
            LOGGER.info("Call disconnected: '%s'" % self.call)

    def hangup_call(self):
        """Hang up the call."""
        LOGGER.info("Hanging up Bob")
        self.call.hangup(code=200, reason="Q.850;cause=16")


class AMICallback(object):
    """Class to register AMI events and callbacks."""

    def __init__(self, test_object):
        self.test_object = test_object
        self.ami = self.test_object.ami[0]
        self.ami.registerEvent('Hangup', self.hangup_event_handler)
        self.ami.registerEvent('BridgeEnter', self.bridge_enter_handler)
        self.ami.registerEvent('BridgeLeave', self.bridge_leave_handler)
        self.alice_in_bridge = False
        self.bob_in_bridge = False
        self.alice_phone_call = None
        self.bob_phone_call = None

    def bridge_enter_handler(self, ami, event):
        """AMI bridge enter event callback."""
        channel = event.get('channel')
        if 'bob' in channel:
            self.bob_in_bridge = True
        elif 'alice' in channel:
            self.alice_in_bridge = True
        if self.bob_in_bridge and self.alice_in_bridge:
            # Prevent multiple transfers if other channels join
            if 'alice' not in channel and 'bob' not in channel:
                return
            LOGGER.info('Both Alice and Bob are in bridge; starting transfer')
            self.alice_phone_call.transfer_call()

    def bridge_leave_handler(self, ami, event):
        """AMI bridge leave event callback."""
        channel = event.get('channel')
        if 'bob' in channel:
            self.bob_in_bridge = False
        elif 'alice' in channel:
            self.alice_in_bridge = False

    def hangup_event_handler(self, ami, event):
        """AMI hang up event callback."""
        LOGGER.debug("Hangup detected for channel '%s'" % event['channel'])


def make_call(obj, acc, uri):
    """Place a call.

    Keyword Arguments:
    obj AMICallback object
    acc The pjsua_mod.PJsuaAccount object to make the call from
    uri String of SIP URI to dial
    """
    try:
        if 'alice' in acc._obj_name:
            LOGGER.info("Alice is calling '%s'" % uri)
            obj.alice_phone_call = AlicePhoneCallCallback()
            acc.make_call(uri, cb=obj.alice_phone_call)
        elif 'bob' in acc._obj_name:
            LOGGER.info("Bob is calling '%s'" % uri)
            obj.bob_phone_call = BobPhoneCallCallback()
            acc.make_call(uri, cb=obj.bob_phone_call)
    except pj.Error, err:
        LOGGER.error("Exception: %s" % str(err))


def log_call_info(call_info):
    """Log call info."""
    LOGGER.debug("Call '%s' <-> '%s'" % (call_info.uri, call_info.remote_uri))
    LOGGER.debug("Call state: '%s'; last code: '%s'; last reason: '%s'" %
                 (call_info.state_text,
                  call_info.last_code,
                  call_info.last_reason))


def exec_pjsua(test_object, triggered_by, ari, events):
    """Callback method upon ARI event trigger.

    Keyword Arguments:
    test_object The test object
    triggered_by Object that triggered a call to this method
    ari Object of ari.ARI
    events Dictionary containing ARI event that triggered this callback
    """
    LOGGER.info("Executing PJSUA.")
    alice = PJSUA_ACCOUNTS.get('alice')
    bob = PJSUA_ACCOUNTS.get('bob')
    obj = AMICallback(test_object)
    if URI['alice'].get('call_uri'):
        lock = alice.pj_lib.auto_lock()
        make_call(obj, alice.account, URI['alice']['call_uri'])
        del lock
    if URI['bob'].get('call_uri'):
        lock = bob.pj_lib.auto_lock()
        make_call(obj, bob.account, URI['bob']['call_uri'])
        del lock

    return True


def pjsua_initialized(test_object, accounts):
    """Callback method upon all PJSUA endpoints being registered.

    Keyword Arguments:
    test_object The test object
    accounts Dictionary of PJSUA account names and pjsua_mod.PJsuaAccount
             objects
    """
    global PJSUA_ACCOUNTS
    PJSUA_ACCOUNTS = accounts
    LOGGER.info("PJSUA Initialized.")


# vim:sw=4:ts=4:expandtab:textwidth=79
