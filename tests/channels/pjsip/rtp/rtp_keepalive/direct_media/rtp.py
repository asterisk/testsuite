'''
Copyright (C) 2015, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''
import logging

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)

class RTP(DatagramProtocol):
    def __init__(self, test_object):
        self.test_object = test_object

    def datagramReceived(self, data, addr):
        LOGGER.error("Received RTP from Asterisk unexpectedly")
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()

class KeepaliveCheck(object):
    def __init__(self, module_config, test_object):
        reactor.listenUDP(25552, RTP(test_object))
        reactor.listenUDP(55225, RTP(test_object))
