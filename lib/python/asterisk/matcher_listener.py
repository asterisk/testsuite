"""Module that match messages and events for a defined listener.

Copyright (C) 2018, Digium, Inc.
Kevin Harwell <kharwell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
import re

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor

from .matcher import PluggableConditions

LOGGER = logging.getLogger(__name__)


class UdpProtocol(DatagramProtocol):
    """Protocol to use for receiving messages."""

    def __init__(self, server):
        """Constructor.

        Keyword Arguments:
        server - The udp server object
        config - Configuration used by the protocol
        """

        self.server = server

    def datagramReceived(self, datagram, address):
        """Receive incoming data.

        Keyword Arguments:
        datagram - The data that was received
        address - The address that the data came from
        """

        LOGGER.debug('Received %s from %s', datagram, address)
        self.server.handle_message(datagram)


class Udp(PluggableConditions):
    """Pluggable module that that checks messages received over UDP"""

    def __init__(self, config, test_object, on_match=None):
        """Constructor

        Keyword Arguments:
        config - configuration for this module
        test_object - the TestCase driver
        on_match - Optional callback called upon a conditional match
        """

        super(Udp, self).__init__(config, test_object, on_match)

        self.filter_msgs = config.get('filter', ['stasis.message', 'channels.'])

        if not isinstance(self.filter_msgs, list):
            self.filter_msgs = [self.filter_msgs]

        reactor.listenUDP(config.get('port', 8125), UdpProtocol(self))

    def handle_message(self, msg):
        """Handle messages received over udp and check the message against the
        configured conditions.

        Keyword Arguments:
        msg -- The message received via the udp
        """

        msgstring = msg.decode('utf8')
        if not any(f for f in self.filter_msgs if re.match(f, msgstring)):
            self.check(msg)


class Ari(PluggableConditions):
    """Pluggable module that that checks messages received over ARI"""

    def __init__(self, config, test_object, on_match=None):
        """Constructor

        Keyword Arguments:
        config - configuration for this module
        test_object - the TestCase driver
        on_match - Optional callback called upon a conditional match
        """

        super(Ari, self).__init__(config, test_object, on_match)

        test_object.register_ws_event_handler(self.check)
