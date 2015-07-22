'''
Copyright (C) 2015, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging
import sys
import time

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor

from construct import *

sys.path.append('lib/python')

LOGGER = logging.getLogger(__name__)


class RTP(DatagramProtocol):
    def __init__(self, test_object):
        self.last_rx_time = None
        self.test_object = test_object
        self.test_object.register_stop_observer(self.asterisk_stopped)

    def datagramReceived(self, data, (host, port)):
        header = Struct('rtp_packet',
                        BitStruct('header',
                                  BitField('version', 2),
                                  Bit('padding'),
                                  Bit('extension'),
                                  Nibble('csrc_count'),
                                  Bit('marker'),
                                  BitField('payload', 7)
                                  ),
                        UBInt16('sequence_number'),
                        UBInt32('timestamp'),
                        UBInt32('ssrc')
                        )
        rtp_header = header.parse(data)
        LOGGER.debug("Parsed RTP packet is {0}".format(rtp_header))
        if rtp_header.header.payload == 13:
            current_time = time.time()
            # Don't compare intervals on the first received CNG
            if self.last_rx_time:
                interval = current_time - self.last_rx_time
                if interval < 2.5 or interval > 3.5:
                    LOGGER.error(
                        "Interval of CNG packets not in tolerance {0}".format(
                            interval))
                    self.test_object.set_passed(False)
                    self.test_object.stop_reactor()
            self.last_rx_time = current_time

    def asterisk_stopped(self, result):
        LOGGER.debug("Asterisk is stopped")
        if self.last_rx_time is None:
            LOGGER.error("Never received any CNG packets during test")
            self.test_object.set_passed(False)
        self.test_object.set_passed(True)


class KeepaliveCheck(object):
    def __init__(self, module_config, test_object):
        reactor.listenUDP(33623, RTP(test_object))
