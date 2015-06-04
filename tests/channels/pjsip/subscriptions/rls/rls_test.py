#/usr/bin/env python
"""
Copyright (C) 2015, Digium, Inc.
Jonathan Rose <jrose@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging

sys.path.append('lib/python')
sys.path.append('tests/channels/pjsip/subscriptions/rls')

from pcap import VOIPListener
from rls_integrity import RLSValidator
from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)


class IntegrityCheck(VOIPListener):
    """Verifies that SIP notifies contain expected updates

       A test module that observes incoming SIP notifies and compares them
       to a set of expected results. Tests may optionally specify for an
       arbitrary number of AMI actions to be executed in order at 2 second
       intervals from the start of the test.
    """
    def __init__(self, module_config, test_object):
        """Constructor

        Arguments:
        module_config Dictionary containing test configuration
        test_object used to manipulate reactor and set/remove failure tokens
        """
        self.set_pcap_defaults(module_config)
        VOIPListener.__init__(self, module_config, test_object)

        self.test_object = test_object
        self.token = test_object.create_fail_token("Haven't handled all "
                                                   "expected NOTIFY packets.")

        self.resources = module_config['resources']
        self.list_name = module_config['list_name']
        self.full_state = module_config['full_state']
        self.ami_action = module_config.get('ami_action')
        self.stop_after_notifys = module_config.get('stop_after_notifys', True)

        self.version = 0
        self.ami = None
        self.test_object.register_ami_observer(self.ami_connect)
        if hasattr(self.test_object, 'register_scenario_started_observer'):
            self.test_object.register_scenario_started_observer(
                self.scenario_started)
        self.add_callback('SIP', self.multipart_handler)

    def set_pcap_defaults(self, module_config):
        """Sets default values for the PcapListener
        """
        if not module_config.get('bpf-filter'):
            module_config['bpf-filter'] = 'udp port 5061'
        if not module_config.get('register-observer'):
            module_config['register-observer'] = True
        if not module_config.get('debug-packets'):
            module_config['debug-packets'] = True
        if not module_config.get('device'):
            module_config['device'] = 'lo'

    def multipart_handler(self, packet):
        """Handles incoming SIP packets and verifies contents

        Checks to see if a packet is a NOTIFY packet with a multipart body.
        Provided that all the basic checks pass, creates and RLSValidator for
        the packet that will verify that the contents of the NOTIFY match the
        expectations set for NOTIFY in the test configuration.

        Arguments:
        packet Incoming SIP Packet
        """

        LOGGER.debug('Received SIP packet')

        if 'NOTIFY' not in packet.request_line:
            LOGGER.debug('Ignoring packet, is not a NOTIFY')
            return

        if packet.body.packet_type != 'Multipart':
            LOGGER.debug('Ignoring packet, NOTIFY does not contain ' +
                         'multipart body')
            return

        if self.version >= len(self.resources):
            LOGGER.debug('Ignoring packet, version is higher than count of ' +
                         'test expectations')
            return

        validator = RLSValidator(test_object=self.test_object,
                                 packet=packet,
                                 version=self.version,
                                 full_state=self.full_state[self.version],
                                 list_name=self.list_name,
                                 resources=self.resources[self.version])

        debug_msg = "validating packet -- expecting {0}"
        LOGGER.debug(debug_msg.format(self.resources[self.version]))
        if not validator.check_integrity():
            LOGGER.error('Integrity Check Failed.')
            return

        info_msg = "Packet validated successfully. Test Phase {0} Completed."
        LOGGER.info(info_msg.format(self.version))
        self.version += 1

        if self.version == len(self.resources):
            info_msg = "All test phases completed. RLS verification complete."
            LOGGER.info(info_msg)
            self.test_object.remove_fail_token(self.token)
            if self.stop_after_notifys:
                # We only deal with as many NOTIFIES as we have resources
                self.test_object.set_passed(True)
                self.test_object.stop_reactor()

    def ami_connect(self, ami):
        """Callback when AMI connects. Sets test AMI instance."""
        self.ami = ami

    def scenario_started(self, scenario):
        """Callback when SIPp scenario has started.

        If this test executes AMI actions, this function will execute
        those AMI actions at two second intervals.

        Note: Overrides scenario_started from VOIPListener

        Arguments:
        scenario Not actually used, just part of the signature.
        """
        def _perform_ami_action():
            action = self.ami_action.pop(0)
            debug_msg = "Sending AMI action: {0}"
            LOGGER.debug(debug_msg.format(action))
            self.ami.sendMessage(action)
            if len(self.ami_action):
                reactor.callLater(2, _perform_ami_action)

        if self.ami_action and len(self.ami_action):
            reactor.callLater(2, _perform_ami_action)
