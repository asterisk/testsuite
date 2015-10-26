#/usr/bin/env python
"""
Copyright (C) 2015, Digium, Inc.
Jonathan Rose <jrose@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging

sys.path.append("lib/python")
sys.path.append("tests/channels/pjsip/subscriptions/rls")

from pcap import VOIPListener
from rls_element import RLSPacket
from rls_validation import ValidationInfo
from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)

def filter_multipart_packet(packet):
    """Determines if a packet is an RLS multipart packet.

    Keyword Arguments:
    packet                  -- A yappcap.PcapPacket

    Returns:
    True if this is a multipart NOTIFY packet. Otherwise, returns False.
    """

    # If the packet is not a SIP NOTIFY, this is not a packet we care
    # about.
    if "NOTIFY" not in packet.request_line:
        LOGGER.debug("Ignoring packet, is not a NOTIFY")
        return False

    # If the packet body is not a multipart packet body, this is not a
    # packet we care about.
    if packet.body.packet_type != "Multipart":
        LOGGER.debug("Ignoring packet, NOTIFY does not contain " \
                     "multipart body")
        return False

    return True

def log_packet(packet, write_packet_contents):
    """Writes the contents of a SIP packet to the log.

    Keyword Arguments:
    packet                  -- A yappcap.PcapPacket
    write_packet_contents   -- Whether or not to dump the contents of the
                               packet to the log.
    """

    message = "Received SIP packet:\n"

    if not write_packet_contents:
        return

    for attr in dir(packet):
        message += "%s = %s\n" % (attr, getattr(packet, attr))
        if attr == "body":
            message += "body:\n"
            body = getattr(packet, attr)
            for body_attr in dir(body):
                value = getattr(body, body_attr)
                message += "\t%s = %s\n" % (body_attr, value)
                message += "%s = %s\n" % (attr, getattr(packet, attr))

    LOGGER.debug(message)

def set_pcap_defaults(module_config):
    """Sets default values for the PcapListener."""

    if not module_config.get("bpf-filter"):
        module_config["bpf-filter"] = "udp port 5061"
    if not module_config.get("register-observer"):
        module_config["register-observer"] = True
    if not module_config.get("debug-packets"):
        module_config["debug-packets"] = True
    if not module_config.get("device"):
        module_config["device"] = "lo"


class RLSTest(VOIPListener):
    """Verifies that SIP notifies contain expected updates.

       A test module that observes incoming SIP notifies and compares them
       to a set of expected results. Tests may optionally specify for an
       arbitrary number of AMI actions to be executed in order at 2 second
       intervals from the start of the test.
    """

    def __init__(self, module_config, test_object):
        """Constructor.

        Keyword Arguments:
        module_config          -- Dictionary containing test configuration.
        test_object            -- Used to manipulate reactor and set/remove
                                  failure tokens.
        """

        set_pcap_defaults(module_config)
        super(RLSTest, self).__init__(module_config, test_object)

        self.test_object = test_object
        self.ami_action = module_config.get("ami-action")

        if self.check_prerequisites():
            self.test_object.register_scenario_started_observer(
                self.on_scenario_started)

        self.ami = None
        self.packets_idx = 0
        self.list_name = module_config["list-name"]
        self.log_packets = module_config.get("log-packets", False)
        self.packets = module_config["packets"]

        self.stop_test_after_notifys = \
            module_config.get("stop-test-after-notifys", True)

        token_msg = "Test execution was interrupted before all NOTIFY " \
                    "packets were accounted for."
        self.token = self.test_object.create_fail_token(token_msg)

        self.test_object.register_ami_observer(self.on_ami_connect)
        self.add_callback("SIP", self.multipart_handler)

    def check_prerequisites(self):
        """Checks the test_object can support an ami_action, if configured.

        Note: This method will fail the test if it is determined that the
        test has a dependency on an ami_action but uses a test object that
        does not have a definition for 'register_scenario_started_observer'.

        Returns:
        True if the test object supports 'register_scenario_started_observer'.
        Otherwise, returns False.
        """

        is_start_observer = hasattr(self.test_object,
                                    "register_scenario_started_observer")
        if self.ami_action is not None:
            message = "This test is configured with an ami_action " \
                      "attribute. However, it is also configured to " \
                      "use a test-object that does not contain support " \
                      "for 'register_scenario_started_observer'. As a " \
                      "result, the ami_action will never be executed. " \
                      "Either reconfigure the test to run without a " \
                      "dependency for an ami_action or change the " \
                      "test-object type to a type that supports " \
                      "'register_scenario_started_observer'."
            self.fail_test(message)

        return is_start_observer

    def fail_test(self, message):
        """Marks the test as failed and stops the reactor.

        Keyword Arguments:
        message                -- Reason for the test failure"""

        LOGGER.error(message)
        self.test_object.remove_fail_token(self.token)
        self.token = self.test_object.create_fail_token(message)
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()

    def multipart_handler(self, packet):
        """Handles incoming SIP packets and verifies contents

        Checks to see if a packet is a NOTIFY packet with a multipart body.
        Provided that all the basic checks pass, creates and RLSValidator for
        the packet that will verify that the contents of the NOTIFY match the
        expectations set for NOTIFY in the test configuration.

        Keyword Arguments:
        packet                 -- Incoming SIP Packet
        """

        log_packet(packet, self.log_packets)

        if not filter_multipart_packet(packet):
            return

        if self.packets_idx >= len(self.packets):
            message = "Received more packets ({0}) than expected ({1}). " \
                      "Failing test.".format(self.packets_idx,
                                             len(self.packets))
            self.fail_test(message)

        rls_packet = RLSPacket(packet)
        resources = self.packets[self.packets_idx]["resources"]
        fullstate = self.packets[self.packets_idx]["full-state"]

        info = ValidationInfo(resources=resources,
                              version=self.packets_idx,
                              fullstate=fullstate,
                              rlmi=None,
                              rlmi_name=self.list_name)

        message = "Validating Resource ({0}) of ({1})..."
        LOGGER.debug(message.format(self.packets_idx, len(self.packets) - 1))

        if not rls_packet.validate(info):
            message = "Integrity Check Failed for Resource ({0})."
            self.fail_test(message.format(self.packets_idx))
            return

        info_msg = "Resource ({0}) validated successfully."
        LOGGER.info(info_msg.format(self.packets_idx))
        self.packets_idx += 1

        if self.packets_idx == len(self.packets):
            info_msg = "All test phases completed. RLS verification complete."
            LOGGER.info(info_msg)
            self.test_object.remove_fail_token(self.token)
            if self.stop_test_after_notifys:
                # We only deal with as many NOTIFIES as we have defined in our
                # test-config.yaml
                self.test_object.set_passed(True)
                self.test_object.stop_reactor()

    def on_ami_connect(self, ami):
        """Callback when AMI connects. Sets test AMI instance."""
        self.ami = ami

    def on_scenario_started(self, scenario):
        """Callback when SIPp scenario has started.

        If this test executes AMI actions, this function will execute
        those AMI actions at two second intervals.

        Note: Overrides scenario_started from VOIPListener

        Keyword Arguments:
        scenario               -- The event payload. (Not actually used, just
                                  part of the signature.)
        """

        def _perform_ami_action():
            """Helper function to loop executing an ami action."""

            action = self.ami_action.pop(0)
            debug_msg = "Sending AMI action: {0}"
            LOGGER.debug(debug_msg.format(action))
            self.ami.sendMessage(action)
            if len(self.ami_action):
                reactor.callLater(2, _perform_ami_action)

        if self.ami_action and len(self.ami_action):
            reactor.callLater(2, _perform_ami_action)
