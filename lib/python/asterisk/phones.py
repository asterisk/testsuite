#!/usr/bin/env python
"""Pluggable modules and classes to simulate phones.

Copyright (C) 2015, Digium, Inc.
John Bigelow <jbigelow@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging
from twisted.internet import reactor
import pjsua as pj

import pjsua_mod

LOGGER = logging.getLogger(__name__)


class PjsuaPhoneController(pjsua_mod.PJsua):
    """Pluggable module class derived from pjsua_mod.PJsua.

    This initializes, sets up callbacks, and keeps track of phones once all
    have registered.
    """

    __singleton_instance = None

    @staticmethod
    def get_instance():
        """Return the singleton instance of the application test_object"""
        if (PjsuaPhoneController.__singleton_instance is None):
            # Note that the constructor sets the singleton instance.
            # This is a tad backwards, but is needed for the pluggable
            # framework. If we get a get_instance call before its been set,
            # blow up - that really shouldn't ever happen
            raise Exception()
        return PjsuaPhoneController.__singleton_instance

    def __init__(self, instance_config, test_object):
        """Constructor"""
        super(PjsuaPhoneController, self).__init__(instance_config,
                                                   test_object)
        self.__pjsua_phones = {}

        if (PjsuaPhoneController.__singleton_instance is None):
            PjsuaPhoneController.__singleton_instance = self
        LOGGER.info("Pluggable module initialized.")

    def reg_success(self):
        """Override of parent callback method.

        Callback for when all PJSUA accounts have registered to Asterisk.
        """
        self.num_regs += 1
        if self.num_regs != self.num_accts:
            return

        for account in self.config['accounts']:
            pjsua_phone = PjsuaPhone(self, account)
            self.__pjsua_phones[account['name']] = pjsua_phone

        LOGGER.info("PJSUA Accounts Registered.")
        self.__setup_pjsua_acc_cb()

    def __setup_pjsua_acc_cb(self):
        """Setup PJSUA account callbacks"""
        for name, phone_obj in self.__pjsua_phones.iteritems():
            acc_cb = AccCallback()
            phone_obj.account.set_callback(acc_cb)
            LOGGER.info("%s is ready to receive calls." % name)

    def get_phone_obj(self, name=None, account=None):
        """Get PjsuaPhone object

        Keyword Arguments:
        name String of account name
        account Object of account

        Returns object of PjsuaPhone.
        """
        if name:
            return self.__pjsua_phones.get(name)
        if account:
            for name, phone_obj in self.__pjsua_phones.iteritems():
                if account is phone_obj.account:
                    return phone_obj


class PjsuaPhone(object):
    """Class to make, transfer, and track calls from the PJSUA account"""

    def __init__(self, controller, account_config):
        """Constructor"""
        self.name = account_config['name']
        self.account = controller.pj_accounts[self.name].account
        self.pj_lib = controller.pj_accounts[self.name].pj_lib
        # List of Call objects
        self.calls = []

    def make_call(self, uri):
        """Place a call.

        Keyword Arguments:
        uri String of SIP URI to dial

        Returns call object
        """
        call = None
        try:
            LOGGER.info("'%s' is calling '%s'" % (self.name, uri))
            call_cb = PhoneCallCallback()
            call = self.account.make_call(uri, cb=call_cb)
            self.calls.append(call)
        except pj.Error as err:
            raise Exception("Exception occurred while making call: '%s'" %
                            str(err))

        return call

    def blind_transfer(self, transfer_uri):
        """Do a blind transfer.

        Keyword Arguments:
        transfer_uri SIP URI of transfer target.
        """
        LOGGER.info("'%s' is transfering (blind) '%s' to '%s'." %
                    (self.name, self.calls[0].info().remote_uri, transfer_uri))
        try:
            self.calls[0].transfer(transfer_uri)
        except pj.Error as err:
            raise Exception("Exception occurred while transferring: '%s'" %
                            str(err))

    def attended_transfer(self):
        """Do an attended transfer.

        The first call will be transfered to the second call.
        """
        LOGGER.info("'%s' is transfering (attended) '%s' to '%s'." %
                    (self.name, self.calls[0].info().remote_uri,
                     self.calls[1].info().remote_uri))
        try:
            self.calls[0].transfer_to_call(self.calls[1], hdr_list=None,
                                           options=0)
        except pj.Error as err:
            raise Exception("Exception occurred while transferring: '%s'" %
                            str(err))


class AccCallback(pj.AccountCallback):
    """Derived callback class for accounts."""

    def __init__(self, account=None):
        pj.AccountCallback.__init__(self, account)

    def on_incoming_call(self, call):
        """Callback for an incoming call.

        Upon an incoming call this sets a callback for the call and is then
        answered.
        """
        controller = PjsuaPhoneController.get_instance()
        phone = controller.get_phone_obj(account=call.info().account)
        phone.calls.append(call)
        LOGGER.info("Incoming call for '%s' from '%s'." %
                    (phone.name, call.info().remote_uri))
        call_cb = PhoneCallCallback(call)
        call.set_callback(call_cb)
        call.answer(200)


class PhoneCallCallback(pj.CallCallback):
    """Derived callback class for calls."""

    def __init__(self, call=None):
        pj.CallCallback.__init__(self, call)
        self.controller = PjsuaPhoneController.get_instance()
        self.phone = None
        if call is not None:
            self.phone = \
                self.controller.get_phone_obj(account=call.info().account)

    def on_state(self):
        """Callback for call state changes.

        Upon a call being disconnected the tracking of the call is removed.
        """
        if self.phone is None:
            self.phone = \
                self.controller.get_phone_obj(account=self.call.info().account)
        LOGGER.debug(fmt_call_info(self.call.info()))
        if self.call.info().state == pj.CallState.CONFIRMED:
            LOGGER.info("Call is up: '%s'" % self.call)

        if self.call.info().state == pj.CallState.DISCONNECTED:
            LOGGER.info("Call disconnected: '%s'" % self.call)
            sip_call_id = self.call.info().sip_call_id
            obj = next((call for call in self.phone.calls
                          if call.info().sip_call_id == sip_call_id), None)
            try:
                self.phone.calls.remove(obj)
            except ValueError:
                pass

    def on_transfer_status(self, code, reason, final, cont):
        """Callback for the status of a previous call transfer request."""
        LOGGER.debug(fmt_call_info(self.call.info()))
        status_format = "\n=== Transfer Status ==="
        status_format += "\nCode: '%s'"
        status_format += "\nReason: '%s'"
        status_format += "\nFinal Notification: '%s'\n"
        LOGGER.debug(status_format % (code, reason, final))
        if final != 1:
            return cont

        LOGGER.debug("Call uri: '%s'; remote uri: '%s'" %
                     (self.call.info().uri, self.call.info().remote_uri))
        if code == 200 and reason == "OK" and cont == 0:
            LOGGER.info("Transfer target answered the call.")
        else:
            LOGGER.warn("Transfer failed!")

        try:
            LOGGER.info("Hanging up '%s'" % self.call)
            self.call.hangup(code=200, reason="Q.850;cause=16")
        except pj.Error as err:
            LOGGER.warn("Failed to hangup the call!")
            LOGGER.warn("Exception: %s" % str(err))

        return cont

    def on_replace_request(self, code, reason):
        """Callback for when an INVITE with a Replaces header is received."""
        LOGGER.debug(fmt_call_info(self.call.info()))
        LOGGER.info("Accepting Replaces request")
        return (code, reason)

    def on_replaced(self, new_call):
        """Callback for when call is being replaced."""
        LOGGER.debug(fmt_call_info(self.call.info()))
        LOGGER.info("Call is being replaced with '%s'" % new_call)

    def on_transfer_request(self, dst, code):
        """Callback for when call is being transfered by remote party"""
        LOGGER.debug(fmt_call_info(self.call.info()))
        LOGGER.info("Accepting transfer request from '%s'" % dst)
        return 202


def fmt_call_info(call_info):
    """Format call info for logging"""
    info_format = "\n=== Call Info ==="
    info_format += "\nCall-ID: '%s'"
    info_format += "\nLocal URI: '%s'"
    info_format += "\nRemote URI: '%s'"
    info_format += "\nState: '%s'"
    info_format += "\nLast Code: '%s'"
    info_format += "\nLast Reason: '%s'\n"
    return info_format % (call_info.sip_call_id, call_info.uri,
                          call_info.remote_uri, call_info.state_text,
                          call_info.last_code, call_info.last_reason)

def call(test_object, triggered_by, ari, event, args):
    """Pluggable action module callback to make a call"""
    controller = PjsuaPhoneController.get_instance()
    phone = controller.get_phone_obj(name=args['pjsua_account'])
    call_uri = args['call_uri']
    if phone is None:
        LOGGER.debug("Phone not initialized. Delaying call.")
        reactor.callLater(1, call, test_object, triggered_by, ari, event, args)
        return

    try:
        phone.make_call(call_uri)
    except:
        test_object.stop_reactor()
        raise Exception("Exception: '%s'" % str(sys.exc_info()))

def transfer(test_object, triggered_by, ari, event, args):
    """Pluggable action module callback to transfer a call"""
    controller = PjsuaPhoneController.get_instance()
    phone = controller.get_phone_obj(name=args['pjsua_account'])
    transfer_type = args['transfer_type']
    transfer_uri = args.get('transfer_uri')
    res = False
    msg = None

    if transfer_type == "attended":
        if len(phone.calls) == 2:
            try:
                phone.attended_transfer()
                res = True
            except:
                msg = "Exception: '%s'" % str(sys.exc_info())
        else:
            msg = "'%s' must have 2 active calls to transfer" % phone.name
    elif transfer_type == "blind":
        if transfer_uri is None:
            msg = "Transfer URI not found!"
        elif len(phone.calls) == 1:
            try:
                phone.blind_transfer(transfer_uri)
                res = True
            except:
                msg = "Exception: '%s'" % str(sys.exc_info())
        else:
            msg = "'%s' must have 1 active call to transfer" % phone.name
    else:
        msg = "Unknown transfer type"

    if not res:
        test_object.stop_reactor()
        raise Exception(msg)

