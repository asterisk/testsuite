"""Verify that an ICE-Lite endpoint does not originate connectivity checks.

Copyright (C) 2026, Greg Anthony

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging

from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol

LOGGER = logging.getLogger(__name__)


class IceLiteListener(DatagramProtocol):
    """Listen on the offered candidate port for STUN Binding requests."""

    def __init__(self, test_object):
        self.test_object = test_object

    def datagramReceived(self, data, addr):
        if len(data) < 8 or data[0:2] != b'\x00\x01':
            return

        if data[4:8] != b'\x21\x12\xa4\x42':
            return

        LOGGER.error("Received a STUN Binding request from %s:%s", *addr)
        self.test_object.set_passed(False)


class IceLiteCheck:
    """A pluggable module that monitors the remote ICE candidate."""

    def __init__(self, module_config, test_object):
        reactor.listenUDP(9000, IceLiteListener(test_object), interface='127.0.0.1')
