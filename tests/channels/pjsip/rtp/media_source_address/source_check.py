'''
Copyright (C) 2026, Arcadiy Ivanov
Arcadiy Ivanov <arcadiy@ivanov.biz>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''
import logging
import struct

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor, task

LOGGER = logging.getLogger(__name__)

# 20 ms of PCMU silence
PAYLOAD = b'\xff' * 160

# Packets a listener waiting for a marker must receive after it: half a
# second of media
MIN_AFTER_MARKER = 25


class MediaListener(DatagramProtocol):
    """Counts the datagrams received on a media port, by source address

    With 'stream' set, once something arrives the listener streams RTP back
    to its sender from the advertised port, so that Asterisk has media to
    relay to the other party of the call. With 'after' set, it also counts
    the datagrams that arrive after the marker of that name.
    """

    def __init__(self, name, stream, after, stream_failed):
        self.name = name
        self.stream = stream
        self.after = after
        self.stream_failed = stream_failed
        self.sources = {}
        self.marked = False
        self.after_count = 0
        self.target = None
        self.seq = 0
        self.loop = None

    def datagramReceived(self, data, addr):
        (host, port) = addr
        self.sources[host] = self.sources.get(host, 0) + 1
        if self.marked:
            self.after_count += 1
        if self.stream and not self.target:
            self.target = addr
            self.loop = task.LoopingCall(self.send)
            self.loop.start(0.02).addErrback(self.stream_failed, self.name)

    def send(self):
        self.seq += 1
        header = struct.pack('!BBHII', 0x80, 0, self.seq & 0xffff,
                             (self.seq * 160) & 0xffffffff, 0x5ec0c4ec)
        self.transport.write(header + PAYLOAD, self.target)

    def stop(self):
        if self.loop and self.loop.running:
            self.loop.stop()


class MarkerListener(DatagramProtocol):
    """Receives markers, names the SIPp scenarios send when something happens

    A scenario sends one with an exec action (see erin.xml), whose command
    has no brackets, which SIPp would take for keywords.
    """

    def __init__(self, listeners):
        self.listeners = listeners

    def datagramReceived(self, data, addr):
        name = data.decode(errors='replace').strip()
        LOGGER.info("Marker %s received" % name)
        for listener in self.listeners:
            if listener.after == name:
                listener.marked = True


class SourceCheck(object):
    """Pluggable module checking the source address of media sent by Asterisk

    Listens on each configured media port (the ports the SIPp scenarios
    advertise in SDP) and, when the test stops, verifies that something was
    received on every port and that all of it came from the expected address.
    Listeners waiting for a marker must also have received media after it.
    """

    def __init__(self, module_config, test_object):
        self.test_object = test_object
        self.expected = module_config['expected-address']
        self.listeners = []
        for listener in module_config['listeners']:
            protocol = MediaListener(listener['name'],
                                     listener.get('stream', False),
                                     listener.get('after'),
                                     self.stream_failed)
            reactor.listenUDP(listener['port'], protocol,
                              interface=listener.get('address', '127.0.0.1'))
            self.listeners.append(protocol)
        markers = module_config.get('markers')
        if markers:
            reactor.listenUDP(markers['port'], MarkerListener(self.listeners),
                              interface=markers.get('address', '127.0.0.1'))
        test_object.register_stop_observer(self.check)

    def stream_failed(self, failure, name):
        LOGGER.error("%s: streaming failed: %s" % (name, failure.getErrorMessage()))
        self.test_object.set_passed(False)

    def check(self, result):
        for listener in self.listeners:
            listener.stop()
            if not listener.sources:
                LOGGER.error("%s: nothing received" % listener.name)
                self.test_object.set_passed(False)
                continue
            for (host, count) in listener.sources.items():
                if host != self.expected:
                    LOGGER.error("%s: %d packets from %s, expected %s" %
                                 (listener.name, count, host, self.expected))
                    self.test_object.set_passed(False)
                else:
                    LOGGER.info("%s: %d packets from %s" %
                                (listener.name, count, host))
            if not listener.after:
                continue
            if not listener.marked:
                LOGGER.error("%s: marker %s not received" %
                             (listener.name, listener.after))
                self.test_object.set_passed(False)
            elif listener.after_count < MIN_AFTER_MARKER:
                LOGGER.error("%s: %d packets after %s, expected at least %d" %
                             (listener.name, listener.after_count,
                              listener.after, MIN_AFTER_MARKER))
                self.test_object.set_passed(False)
            else:
                LOGGER.info("%s: %d packets after %s" %
                            (listener.name, listener.after_count,
                             listener.after))
        return result
