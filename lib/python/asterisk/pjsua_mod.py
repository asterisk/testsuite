#!/usr/bin/env python
"""PJSUA wrapper classes and pluggable modules

Copyright (C) 2014, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging
import socket

import pjsua as pj

sys.path.append("lib/python")

from twisted.internet import reactor
from .test_runner import load_and_parse_module

LOGGER = logging.getLogger(__name__)


class RegDetector(pj.AccountCallback):
    """
    Class that detects PJSUA account registration

    This is a subclass of pj.AccountCallback and is set as the callback class
    for PJSUA accounts by the pluggable module.

    The only method that is overridden is the on_reg_state method, which is
    called when the registration state of an account changes. When all
    configured accounts have registered, then the configured callback method
    for the test is called into.
    """
    def __init__(self, test_plugin):
        self.test_plugin = test_plugin
        pj.AccountCallback.__init__(self)

    def on_reg_state(self):
        """
        Method that is called into when an account's registration state
        changes.

        If the registration status is in the 2XX range, then it means the
        account has successfully registered with Asterisk. Once all configured
        accounts have registered, this method will call the configured callback
        method.

        Since on_reg_state is called from PJSUA's thread, the ensuing callback
        to the configured callback is pushed into the reactor thread.
        """
        status = self.account.info().reg_status
        uri = self.account.info().uri

        if status >= 200 and status < 300:
            LOGGER.info("Detected successful registration from %s" % uri)
            reactor.callFromThread(self.test_plugin.reg_success)


class PJsuaAccount(object):
    """
    Wrapper for pj.Account object

    This object contains a reference to a pj.Account and a dictionary of the
    account's buddies, keyed by buddy name
    """
    def __init__(self, account, pj_lib):
        self.account = account
        self.buddies = {}
        self.pj_lib = pj_lib

    def add_buddies(self, buddy_cfg):
        """
        Add configured buddies to the account.

        All buddies are required to have a name and a URI set.
        """
        for buddy in buddy_cfg:
            name = buddy.get('name')
            if not name:
                LOGGER.warning("Unable to add buddy with no name")
                continue

            uri = buddy.get('uri')
            if not uri:
                LOGGER.warning("Unable to add buddy %s. No URI", name)
                continue

            self.buddies[name] = self.account.add_buddy(uri)


class PJsua(object):
    """A class that takes care of the initialization and account creation for
    PJSUA endpoints during a test.

    This class will initiate PJLIB, create any configured accounts, and wait
    for the accounts to register. Once registered, this will call into user
    code so that manipulation of the endpoints may be performed if specified.

    This class will initiate PJLIB and create any configured accounts. Accounts
    can be configured to register or not register on an overall basis (not per
    account). If configured to register (the default), this will call into user
    code once all accounts have registered. If configured not to register, this
    will call into user code once all accounts have been created.
    """

    def __init__(self, instance_config, test_object):
        """Constructor for pluggable modules."""
        super(PJsua, self).__init__()

        self.test_object = test_object
        self.test_object.register_ami_observer(self.__ami_connect)
        self.config = instance_config
        self.pj_transports = {}
        self.pj_accounts = {}
        self.lib = None
        self.num_regs = 0
        self.num_accts = 0
        self.num_accts_created = 0
        self.ami_connected = 0
        self.callback_module = instance_config.get('callback_module')
        self.callback_method = instance_config.get('callback_method')
        # Default is 4. Must be lower than PJSUA_MAX_CALLS (default is 32).
        self.max_calls = 30

    def __ami_connect(self, ami):
        """
        Handler for when AMI has started.

        We use AMI connection as the signal to start creating PJSUA accounts
        and starting PJLIB.
        """
        self.ami_connected += 1
        if (self.ami_connected < len(self.test_object.ami)):
            LOGGER.info("{0} ami connected. Waiting for "
                        "{1}".format(self.ami_connected,
                                     len(self.test_object.ami)))
            return

        ua_cfg = pj.UAConfig()
        ua_cfg.max_calls = self.max_calls
        self.lib = pj.Lib()
        try:
            self.lib.init(ua_cfg=ua_cfg)
            self.__create_transports()
            self.lib.set_null_snd_dev()
            self.__create_accounts()
            self.lib.start()
        except pj.Error as exception:
            LOGGER.error("Exception: " + str(exception))
            self.lib.destroy()
            self.lib = None
            self.test_object.stop_reactor()

    def __create_transport(self, cfg):
        """Create a PJSUA transport from a transport configuration."""
        def __to_pjprotocol(prot_str, is_v6):
            """
            Translate a string protocol to an enumerated type for PJSUA.

            PJSUA's enumerations require both the transport protocol to be used
            and whether IPv6 is being used.
            """
            if prot_str == 'udp':
                if is_v6:
                    return pj.TransportType.UDP_IPV6
                else:
                    return pj.TransportType.UDP
            elif prot_str == 'tcp':
                if is_v6:
                    return pj.TransportType.TCP_IPV6
                else:
                    return pj.TransportType.TCP
            elif prot_str == 'tls':
                if is_v6:
                    LOGGER.error("PJSUA python bindings do not support IPv6"
                                 "with TLS")
                    self.test_object.stop_reactor()
                else:
                    return pj.TransportType.TLS
            else:
                return pj.TransportType.UNSPECIFIED

        protocol = (cfg.get('protocol', 'udp')).lower()
        bind = cfg.get('bind', '127.0.0.1')
        bindport = cfg.get('bindport', '5060')
        public_addr = cfg.get('public_addr', '')
        is_v6 = False

        try:
            socket.inet_pton(socket.AF_INET6, bind)
            is_v6 = True
        except socket.error:
            # Catching an exception just means the address is not IPv6
            pass

        pj_protocol = __to_pjprotocol(protocol, is_v6)
        LOGGER.info("Creating transport config %s:%s" % (bind, bindport))
        transport_cfg = pj.TransportConfig(int(bindport), bind, public_addr)
        return self.lib.create_transport(pj_protocol, transport_cfg)

    def __create_transports(self):
        """
        Create all configured transports

        If no transports are configured, then a single transport, called
        "default" will be created, using address 127.0.0.1, UDP port 5060.
        """
        if not self.config.get('transports'):
            cfg = {
                'name': 'default',
            }
            self.__create_transport(cfg)
            return

        for cfg in self.config['transports']:
            if not cfg.get('name'):
                LOGGER.error("No transport name specified")
                self.test_object.stop_reactor()
            self.pj_transports[cfg['name']] = self.__create_transport(cfg)

    def __create_account(self, acct_cfg):
        """Create a PJSuaAccount from configuration"""
        account_cb = None
        name = acct_cfg['name']
        username = acct_cfg.get('username', name)
        domain = acct_cfg.get('domain', '127.0.0.1')
        password = acct_cfg.get('password', '')

        # If account is not to register to a server then create the config
        # without specifying a domain and set the ID using the domain ourself.
        if not self.config.get('register', True):
            pj_acct_cfg = pj.AccountConfig()
            pj_acct_cfg.id = "%s <sip:%s@%s>" % (name, username, domain)
        else:
            account_cb = RegDetector(self)
            pj_acct_cfg = pj.AccountConfig(domain, username, password, name)

        if acct_cfg.get('mwi-subscribe'):
            pj_acct_cfg.mwi_enabled = 1
        if acct_cfg.get('transport'):
            acct_transport = acct_cfg.get('transport')
            if acct_transport in self.pj_transports:
                transport_id = self.pj_transports[acct_transport]._id
                pj_acct_cfg.transport_id = transport_id

        LOGGER.info("Creating PJSUA account %s@%s" % (username, domain))
        account = PJsuaAccount(self.lib.create_account(pj_acct_cfg, False,
                                                       account_cb), self.lib)
        account.add_buddies(acct_cfg.get('buddies', []))
        return account

    def __create_accounts(self):
        """
        Create all configured PJSUA accounts.

        All accounts must have a name specified. All other parameters will have
        suitable defaults provided if not present. See the sample yaml file for
        default values.
        """
        if not self.config.get('accounts'):
            LOGGER.error("No accounts configured")
            self.test_object.stop_reactor()

        self.num_accts = len(self.config['accounts'])
        for acct in self.config['accounts']:
            name = acct.get('name')
            if not name:
                LOGGER.error("Account configuration has no name")
                self.test_object.stop_reactor()
            self.pj_accounts[name] = self.__create_account(acct)
            self.acct_success()

    def acct_success(self):
        """Count & check number of created PJSUA accounts.

        If accounts will not be registering and all accounts have been created,
        call the configured callback module/method.
        """
        self.verify_callback_config()
        self.num_accts_created += 1
        # Only execute callback when accounts won't be registering. The
        # callback will be executed else where if accounts will be registering.
        if (self.num_accts_created == self.num_accts and
                not self.config.get('register', True)):
            self.do_callback()

    def reg_success(self):
        """Count & check number of registered PJSUA accounts.

        If all accounts have registered, call the configured callback
        module/method.
        """
        self.verify_callback_config()
        self.num_regs += 1
        if self.num_regs == self.num_accts:
            self.do_callback()

    def verify_callback_config(self):
        """Stop the reactor if no callback module or method is configured"""
        if self.callback_module is None or self.callback_method is None:
            LOGGER.error("No callback configured.")
            self.test_object.stop_reactor()
            return

    def do_callback(self):
        """Call the configured callback module/method"""
        callback_method = load_and_parse_module(self.callback_module + '.' + self.callback_method)
        callback_method(self.test_object, self.pj_accounts)
