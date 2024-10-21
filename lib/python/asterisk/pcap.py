#!/usr/bin/env python
"""Asterisk pcap pluggable modules

This module implements a suite of pluggable module for the Asterisk Test Suite
that will generate and manipulate a pcap of the message traffic during a test.

Copyright (C) 2013, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

from codecs import ascii_decode
import sys
import logging
import signal
import argparse
import binascii

sys.path.append('lib/python')

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
from construct import *
from construct.core import *
from asterisk.pcap_proxy import *
try:
    from yappcap import PcapOffline
    PCAP_AVAILABLE = True
except:
    PCAP_AVAILABLE = False

import rlmi

from protocols.ipstack import ip_stack
from pcap_listener import PcapListener as PacketCapturer

LOGGER = logging.getLogger(__name__)


class PcapListener(object):
    """Class that creates a pcap file for a test

    Optionally, this will also provide run-time inspection of the
    received packets
    """

    def __init__(self, module_config, test_object):
        """Constructor

        Keyword arguments:
        module_config The YAML config object for this module
        test_object   The test object this module will attach to
        """
        if not PCAP_AVAILABLE:
            raise Exception('yappcap not installed')

        device = module_config.get('device')
        bpf_filter = module_config.get('bpf-filter')
        filename = module_config.get('filename')
        snaplen = module_config.get('snaplen')
        buffer_size = module_config.get('buffer-size')
        self.debug_packets = module_config.get('debug-packets', False)

        # Let exceptions propagate - if we can't create the pcap, this should
        # throw the exception to the pluggable module creation routines

        PacketCapturer(device, bpf_filter, filename, self.__pcap_callback,
            snaplen, buffer_size)

    def __pcap_callback(self, packet):
        """Private callback that logs packets if the configuration supports it
        """
        if (self.debug_packets):
            LOGGER.debug(str(packet))
        self.pcap_callback(packet)

    def pcap_callback(self, packet):
        """Virtual function for inspecting received packets

        Derived classes should override this to inspect packets as they arrive
        from the listener
        """
        pass

class VOIPListener(VOIPSniffer, PcapListener):
    """Pluggable module class that sniffs for SIP, RTP, and RTCP packets

    Received packets are stored according to the source.

    Attributes:
    packet_factory The one and only PacketFactoryManager
    traces         Dictionary of sniffed message traffic, organized by
                   source address
    """

    def __init__(self, module_config, test_object):
        """Constructor

        Keyword Arguments:
        module_config The module configuration for this pluggable module
        test_object   The object we will attach to
        """

        VOIPSniffer.__init__(self, module_config, test_object)

        packet_type = module_config.get("packet-type")
        bpf = module_config.get("bpf-filter")

        if packet_type:
            self.add_callback(packet_type, module_config.get("callback"))

        PcapListener.__init__(self, module_config, test_object)

    def pcap_callback(self, packet):
        """Packet capture callback function

        Overrides PcapListener's virtual function. This will interpret the
        packet using the PacketFactoryManager, and pass the parsed packet
        off to registered callbacks.

        Keyword Arguments:
        packet A received packet from the pcap listener
        """

        self.process_packet(packet, (None, None))

# This is a unit test for capture and parsing.
# By default it listens on the loopback interface
# UDP port 5060.

if __name__ == "__main__":

    def callback(packet):
        print(packet)

    def signal_handler(sig, frame):
        print('You pressed Ctrl+C!')
        reactor.stop()

    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser(description="pcap unit test")
    parser.add_argument("-i", "--interface", metavar="i", action="store",
                      type=str, dest="interface", default="lo",
                      help="Interface to listen on")
    parser.add_argument("-f", "--filter", metavar="f", action="store",
                      type=str, dest="filter", default="udp port 5060",
                      help="BPF Filter")
    parser.add_argument("-o", "--output", metavar="o", action="store",
                      type=str, dest="output", default="/tmp/pcap_unit_test.pcap",
                      help="Output file")
    options = parser.parse_args()
    print('Listening on "%s", using filter "%s", capturing to "%s"'
          % (options.interface, options.filter, options.output))

    module_config = {
        "device": options.interface,
        "bpf-filter": options.filter,
        "filename": options.output,
        "snaplen": 65535,
        "buffer-size": 0,
        "callback": callback,
        "debug-packets": True,
        "packet-type": "*"
    }
    pcap = VOIPListener(module_config, None)
    reactor.run()