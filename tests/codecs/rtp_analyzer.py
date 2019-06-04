#!/usr/bin/env python
'''
Copyright (C) 2016, Digium, Inc.
Kevin Harwell <kharwell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging

sys.path.append("lib/python")

from asterisk import pcap

LOGGER = logging.getLogger(__name__)


class Analyzer(object):
    """Pluggable module that analyzes incoming RTP packets on a given port
    and verifies the sequence and timestamp difference between each packet.

    Configuration options:
      port: the port RTP is expected to be received on
      time_diff: expected difference between RTP timestamps
      num_packets: number of expected packets
      device: device to listen on
      snaplen: snap length
      bfp-filter: packet filter
      buffer-size: size of the packet buffer
      debug-packets: whether or not to output packets to the log
    """

    def __init__(self, module_config, test_object):
        """Constructor

        Keyword Arguments:
        module_config The module configuration for this pluggable module
        test_object   The object we will attach to
        """

        self._test_object = test_object

        self._last_seqno = 0
        self._last_timestamp = 0
        self._num_packets = 0

        if not module_config:
            module_config = {}

        self._port = int(module_config.get('port', 16001))
        self._time_diff = int(module_config.get('time_diff', 160))
        self._total_packets = int(module_config.get('total_packets', 0))

        pcap_defaults = {
            'device': 'lo',
            'snaplen': 2000,
            'bpf-filter': '',
            'debug-packets': False,
            'buffer-size': 4194304,
            'register-observer': True
        }

        pcap_config = dict(pcap_defaults.items() + module_config.items())

        self._sniffer = pcap.VOIPListener(pcap_config, test_object)
        self._sniffer.add_callback('RTP', self._handle_rtp)

        if self._total_packets:
            self._packets_failure = self._test_object.create_fail_token(
                "Did not receive expected number of packets {0}".format(
                    self._total_packets))

    def _handle_rtp(self, packet):
        """Make sure the time differences between RTP packets is correct."""

        def __handle_error(message):
            """Handle errors"""

            LOGGER.error(message)
            self._test_object.set_passed(False)
            self._test_object.stop_reactor()

        if packet.dst_port != self._port:
            return

        LOGGER.debug("!#### num packets={0}, seqno={1}, last_seq={2}".format(self._num_packets, packet.seqno, self._last_seqno))

        # Ignore the first few packets (There seems to be a bug in the packet
        # capture code where it sometimes drops a few packets near start up).
        if self._num_packets > 40:
            # Fail if packets are out of order
            if packet.seqno - self._last_seqno != 1:
                __handle_error("Bad sequence current={0}, last={1}".format(
                    packet.seqno, self._last_seqno))
                return

            # Fail if the time difference does not also match
            if packet.timestamp - self._last_timestamp != self._time_diff:
                __handle_error("Bad timestamp current={0}, last={1}".format(
                    packet.timestamp, self._last_timestamp))
                return

        self._num_packets += (packet.seqno - self._last_seqno
                              if self._last_seqno else 1)

        self._last_seqno = packet.seqno
        self._last_timestamp = packet.timestamp

        if self._total_packets:
            # Remove the fail token when all packets are received
            if (self._num_packets == self._total_packets):
                self._test_object.remove_fail_token(self._packets_failure)
            # Fail if more packets are received than expected
            elif self._num_packets > self._total_packets:
                __handle_error("Expected {0} packets received {1}".format(
                    self._total_packets, self._num_packets))

