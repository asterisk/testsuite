#/usr/bin/env python

import sys
import logging

sys.path.append('lib/python')
sys.path.append('tests/channels/pjsip/subscriptions/rls')

from pcap import VOIPListener
from rls_integrity import RLSValidator
from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)

class IntegrityCheck(VOIPListener):
    """A test module that observes incoming SIP notifies and compares them
       to a set of expected results. Tests may optionally specify for an
       arbitrary number of AMI actions to be executed in order at 2 second
       intervals from the start of the test.
    """
    def __init__(self, module_config, test_object):
        """Create listener and add AMI observer/callbacks."""
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
        """Set default values for PcapListener module for values that aren't
           explicitly overridden.
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
        """Checks multipart packets to see if NOTIFY messages have
           anticipated data.
        """
        if 'NOTIFY' not in packet.request_line:
            return

        if packet.body.packet_type != 'Multipart':
            return

        if self.version >= len(self.resources):
            return

        validator = RLSValidator(test_object=self.test_object,
                                 packet=packet,
                                 version=self.version,
                                 full_state=self.full_state[self.version],
                                 list_name=self.list_name,
                                 resources=self.resources[self.version])
        validator.check_integrity()
        self.version += 1

        if self.version == len(self.resources):
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

        If this test executes an AMI action, this
        """
        def _perform_ami_action():
            self.ami.sendMessage(self.ami_action.pop(0))
            if len(self.ami_action):
                reactor.callLater(2, _perform_ami_action)

        if self.ami_action and len(self.ami_action):
            reactor.callLater(2, _perform_ami_action)
