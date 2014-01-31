#!/usr/bin/env python
"""Generic pluggable modules

Copyright (C) 2012, Digium, Inc.
Kinsey Moore <kmoore@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging
import socket

sys.path.append("lib/python")
from ami import AMIEventInstance
from twisted.internet import reactor
import pjsua as pj

LOGGER = logging.getLogger(__name__)

class Originator(object):
    """Pluggable module class that originates calls in Asterisk"""

    def __init__(self, module_config, test_object):
        """Initialize config and register test_object callbacks."""
        self.ami = None
        test_object.register_ami_observer(self.ami_connect)
        self.test_object = test_object
        self.current_destination = 0
        self.ami_callback = None
        self.scenario_count = 0
        self.config = {
            'channel': 'Local/s@default',
            'application': 'Echo',
            'data': '',
            'context': '',
            'exten': '',
            'priority': '',
            'ignore-originate-failure': 'no',
            'trigger': 'scenario_start',
            'scenario-trigger-after': None,
            'scenario-name': None,
            'id': '0',
            'async': 'False',
            'event': None,
            'timeout': None,
        }

        # process config
        if not module_config:
            return
        for k in module_config.keys():
            if k in self.config:
                self.config[k] = module_config[k]

        if self.config['trigger'] == 'scenario_start':
            if (self.config['scenario-trigger-after'] is not None and
                    self.config['scenario-name'] is not None):
                LOGGER.error("Conflict between 'scenario-trigger-after' and "
                        "'scenario-name'. Only one may be used.")
                raise Exception
            else:
                test_object.register_scenario_started_observer(
                    self.scenario_started)
        elif self.config['trigger'] == 'event':
            if not self.config['event']:
                LOGGER.error("Event specifier for trigger type 'event' is "
                             "missing")
                raise Exception

            # set id to the AMI id for the origination if it is unset
            if 'id' not in self.config['event']:
                self.config['event']['id'] = self.config['id']

            self.ami_callback = AMIPrivateCallbackInstance(self.config['event'],
                                    test_object, self.originate_callback)
        return

    def ami_connect(self, ami):
        """Handle new AMI connections."""
        LOGGER.info("AMI %s connected" % (str(ami.id)))
        if str(ami.id) == self.config['id']:
            self.ami = ami
            if self.config['trigger'] == 'ami_connect':
                self.originate_call()
        return

    def failure(self, result):
        """Handle origination failure."""

        if self.config['ignore-originate-failure'] == 'no':
            LOGGER.info("Originate failed: %s" % (str(result)))
            self.test_object.set_passed(False)
        return None

    def originate_callback(self, ami, event):
        """Handle event callbacks."""
        LOGGER.info("Got event callback for Origination")
        self.originate_call()
        return True

    def originate_call(self):
        """Originate the call"""
        LOGGER.info("Originating call")

        deferred = None
        if len(self.config['context']) > 0:
            deferred = self.ami.originate(channel=self.config['channel'],
                               context=self.config['context'],
                               exten=self.config['exten'],
                               priority=self.config['priority'],
                               timeout=self.config['timeout'],
                               async=self.config['async'])
        else:
            deferred = self.ami.originate(channel=self.config['channel'],
                               application=self.config['application'],
                               data=self.config['data'],
                               timeout=self.config['timeout'],
                               async=self.config['async'])
        deferred.addErrback(self.failure)

    def scenario_started(self, result):
        """Handle origination on scenario start if configured to do so."""
        LOGGER.info("Scenario '%s' started" % result.name)
        if self.config['scenario-name'] is not None:
            if result.name == self.config['scenario-name']:
                LOGGER.debug("Scenario name '%s' matched" % result.name)
                self.originate_call()
        elif self.config['scenario-trigger-after'] is not None:
            self.scenario_count += 1
            trigger_count = int(self.config['scenario-trigger-after'])
            if self.scenario_count == trigger_count:
                LOGGER.debug("Scenario count has been met")
                self.originate_call()
        else:
            self.originate_call()
        return result


class AMIPrivateCallbackInstance(AMIEventInstance):
    """Subclass of AMIEventInstance that operates by calling a user-defined
    callback function. The callback function returns the current disposition
    of the test (i.e. whether the test is currently passing or failing).
    """

    def __init__(self, instance_config, test_object, callback):
        """Constructor"""
        super(AMIPrivateCallbackInstance, self).__init__(instance_config,
                                                         test_object)
        self.callback = callback
        if 'start' in instance_config:
            self.passed = True if instance_config['start'] == 'pass' else False

    def event_callback(self, ami, event):
        """Generic AMI event handler"""
        self.passed = self.callback(ami, event)
        return (ami, event)

    def check_result(self, callback_param):
        """Set the test status based on the result of self.callback"""
        self.test_object.set_passed(self.passed)
        return callback_param


class AMIChannelHangup(AMIEventInstance):
    """An AMIEventInstance derived class that hangs up a channel when an
    event is matched."""

    def __init__(self, instance_config, test_object):
        """Constructor for pluggable modules"""
        super(AMIChannelHangup, self).__init__(instance_config, test_object)
        self.hungup_channel = False
        self.delay = instance_config.get('delay') or 0

    def event_callback(self, ami, event):
        """Override of the event callback"""
        if self.hungup_channel:
            return
        if 'channel' not in event:
            return
        LOGGER.info("Hanging up channel %s" % event['channel'])
        self.hungup_channel = True
        reactor.callLater(self.delay, ami.hangup, event['channel'])
        return (ami, event)


class AMIChannelHangupAll(AMIEventInstance):
    """An AMIEventInstance derived class that hangs up all the channels when
    an event is matched."""

    def __init__(self, instance_config, test_object):
        """Constructor for pluggable modules"""
        super(AMIChannelHangupAll, self).__init__(instance_config, test_object)
        test_object.register_ami_observer(self.__ami_connect)
        self.channels = []

    def __ami_connect(self, ami):
        """AMI connect handler"""
        if str(ami.id) in self.ids:
            ami.registerEvent('Newchannel', self.__new_channel_handler)
            ami.registerEvent('Hangup', self.__hangup_handler)

    def __new_channel_handler(self, ami, event):
        """New channel event handler"""
        self.channels.append({'id': ami.id, 'channel': event['channel']})

    def __hangup_handler(self, ami, event):
        """Hangup event handler"""
        objects = [x for x in self.channels if (x['id'] == ami.id and
                                            x['channel'] == event['channel'])]
        for obj in objects:
            self.channels.remove(obj)

    def event_callback(self, ami, event):
        """Override of the event callback"""
        def __hangup_ignore(result):
            """Ignore hangup errors"""
            # Ignore hangup errors - if the channel is gone, we don't care
            return result

        objects = [x for x in self.channels if x['id'] == ami.id]
        for obj in objects:
            LOGGER.info("Hanging up channel %s" % obj['channel'])
            ami.hangup(obj['channel']).addErrback(__hangup_ignore)
            self.channels.remove(obj)


class HangupMonitor(object):
    """A class that monitors for new channels and hungup channels. When all
    channels it has monitored for have hung up, it ends the test.

    Essentially, as long as there are new channels it will keep the test
    going; however, once channels start hanging up it will kill the test
    on the last hung up channel.
    """

    def __init__(self, instance_config, test_object):
        """Constructor for pluggable modules"""
        super(HangupMonitor, self).__init__()
        self.__dict__.update(instance_config)
        self.test_object = test_object
        self.test_object.register_ami_observer(self.__ami_connect)
        self.channels = []

    def __ami_connect(self, ami):
        """AMI connect handler"""
        if str(ami.id) in self.ids:
            ami.registerEvent('Newchannel', self.__new_channel_handler)
            ami.registerEvent('Hangup', self.__hangup_handler)

    def __new_channel_handler(self, ami, event):
        """Handler for the Newchannel event"""
        LOGGER.debug("Tracking channel %s" % event['channel'])
        self.channels.append(event['channel'])
        return (ami, event)

    def __hangup_handler(self, ami, event):
        """Handler for the Hangup event"""
        LOGGER.debug("Channel %s hungup" % event['channel'])
        self.channels.remove(event['channel'])
        if len(self.channels) == 0:
            LOGGER.info("All channels have hungup; stopping test")
            self.test_object.stop_reactor()
        return (ami, event)


class RegDetector(pj.AccountCallback):
    """
    Class that detects PJSUA account registration

    This is a subclass of pj.AccountCallback and is set as the callback class
    for PJSUA accounts by the pluggable module.

    The only method that is overridden is the on_reg_state method, which is
    called when the registration state of an account changes. When all
    configured accounts have registered, then the configured callback method
    for the test is called into.

    This means that as written, all PJSUA tests require registration to be
    performed.
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
            self.test_plugin.num_regs += 1

        if self.test_plugin.num_regs == self.test_plugin.num_accts:
            callback_module = __import__(self.test_plugin.callback_module)
            callback_method = getattr(callback_module,
                                      self.test_plugin.callback_method)
            reactor.callFromThread(callback_method,
                                   self.test_plugin.test_object,
                                   self.test_plugin.pj_accounts)


class PJsuaAccount(object):
    """
    Wrapper for pj.Account object

    This object contains a reference to a pj.Account and a dictionary of the
    account's buddies, keyed by buddy name
    """
    def __init__(self, account):
        self.account = account
        self.buddies = {}

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
    code so that manipulation of the endpoints may be performed.
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
        self.ami = None
        self.acct_cb = RegDetector(self)
        self.callback_module = instance_config['callback_module']
        self.callback_method = instance_config['callback_method']

    def __ami_connect(self, ami):
        """
        Handler for when AMI has started.

        We use AMI connection as the signal to start creating PJSUA accounts
        and starting PJLIB.
        """
        self.ami = ami
        self.lib = pj.Lib()
        try:
            self.lib.init()
            self.__create_transports()
            self.lib.set_null_snd_dev()
            self.__create_accounts()
            self.lib.start()
        except pj.Error, exception:
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
        name = acct_cfg['name']
        username = acct_cfg.get('username', name)
        domain = acct_cfg.get('domain', '127.0.0.1')
        password = acct_cfg.get('password', '')

        pj_acct_cfg = pj.AccountConfig(domain, username, password, name)

        LOGGER.info("Creating PJSUA account %s@%s" % (username, domain))
        account = PJsuaAccount(self.lib.create_account(pj_acct_cfg, False,
                                                       self.acct_cb))
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
