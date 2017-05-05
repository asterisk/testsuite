"""
Copyright (C) 2016, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
from twisted.internet import reactor
from twisted.internet.protocol import ClientFactory, Protocol

LOGGER = logging.getLogger(__name__)

AUTH_LIMIT = 1
EXPECTED_CONNECTIONS_MADE = 2
EXPECTED_CONNECTIONS_LOST = EXPECTED_CONNECTIONS_MADE - AUTH_LIMIT


class TCPClient(Protocol):
    def __init__(self, module):
        self.module = module
        self.port = 0

    def connectionLost(self, reason):
        LOGGER.info("Lost connection for source port {0}".format(self.port))
        LOGGER.info("Reason is {0}".format(reason.value))
        self.module.connections_lost += 1

    def connectionMade(self):
        self.port = self.transport.getHost().port
        LOGGER.info("Connection made for source port {0}".format(self.port))
        self.module.connections_made += 1


class TCPClientFactory(ClientFactory):
    def __init__(self, module):
        self.module = module
        self.port = 0

    def buildProtocol(self, addr):
        return TCPClient(self.module)


class TCPClientModule(object):
    def __init__(self, test_config, test_object):
        self.test_object = test_object
        self.connections_made = 0
        self.connections_lost = 0
        test_object.register_ami_observer(self.ami_connect)

    def ami_connect(self, ami):
        reactor.connectTCP("127.0.0.1", 5060, TCPClientFactory(self),
                           bindAddress=("127.0.0.1", 0))
        reactor.connectTCP("127.0.0.1", 5060, TCPClientFactory(self),
                           bindAddress=("127.0.0.1", 0))
        reactor.callLater(5, self.evaluate_connections)

    def evaluate_connections(self):
        LOGGER.info("Made {0} connections".format(self.connections_made))
        LOGGER.info("Lost {0} connections".format(self.connections_lost))
        if (self.connections_made == EXPECTED_CONNECTIONS_MADE and
            self.connections_lost == EXPECTED_CONNECTIONS_LOST):
            self.test_object.set_passed(True)
        else:
            self.test_object.set_passed(False)
        self.test_object.stop_reactor()
