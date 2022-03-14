'''
Copyright (C) 2015, Fairview 5 Engineering, LLC
George Joseph <george.joseph@fairview5.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''
import logging

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)

class RTP(DatagramProtocol):
    packet_count = 0

    def __init__(self, test_object):
        self.test_object = test_object

    def datagramReceived(self, data, addr):
        (host, port) = addr
        if self.packet_count == 0 and host != "127.0.0.3":
            LOGGER.error("Received RTP from wrong ip address: %s %s" % host,port)
            self.test_object.set_passed(False)
        self.packet_count += 1

class PacketSourceCheck(object):
    def __init__(self, module_config, test_object):
        reactor.listenUDP(55225, RTP(test_object))
