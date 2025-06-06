#!/usr/bin/env python

"""A test that creates a media websocket server
   and checks that media echoed back matches what was sent.

Copyright (C) 2025, Sangoma Technologies Corporation
George Joseph <gjoseph@sangoma.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging
import io
import os
from twisted.internet import reactor, threads

sys.path.append("lib/python")
from asterisk.test_case import TestCase
from asterisk.media_websocket import MediaWebSocketServerFactory

LOGGER = logging.getLogger(__name__)

TEST_DIR = os.path.dirname(os.path.realpath(__file__))

class ChanWebSocketTest(TestCase):

    def __init__(self, test_path='', test_config=None):
        super().__init__(test_path, test_config)

        if test_config is None:
            test_config = {}

        self.reactor_timeout = test_config.get('reactor-timeout', 10)
        self.listen_port = test_config.get('listen-port', 56789)
        LOGGER.info(f"Reactor timeout {self.reactor_timeout}")
        LOGGER.info(f"Listen port {self.listen_port}")

        self.sent_buffer = None
        self.recvd_buffer = None
        self.optimal_frame_size = 0
        self.protocol = None
        self.received_xon = False
        self.received_xoff = False

        self.factory = MediaWebSocketServerFactory(self,
                        f"ws://localhost:{self.listen_port}/media",
                        "localhost", protocols=['media'])

        LOGGER.info("Registering startup observer")
        self.register_start_observer(self.on_startup)
        self.create_asterisk()

    def run(self):
        super().run()
        LOGGER.info("Binding websocket server")
        reactor.listenTCP(self.listen_port, self.factory,
                          self.reactor_timeout, "127.0.0.1")

    def on_startup(self, ast):
        LOGGER.info("Asterisk started")
        self.ast = ast
        self.passed = False
        LOGGER.info("Originating call")
        self.ast[0].cli_exec("channel originate WebSocket/media_connection1/c(ulaw)n extension echo@default")

    def on_ws_connect(self, request):
        LOGGER.info("WebSocket connection from %s attempted" % (request.peer))
        self.peer = request.peer
        return "media"

    def on_ws_open(self, protocol):
        LOGGER.info("WebSocket connection from %s opened" % (self.peer))
        self.protocol = protocol

    def on_reactor_timeout(self):
        self.protocol.sendClose(1000)

    def on_ws_closed(self, protocol):
        LOGGER.info("WebSocket connection from %s closed.  Stopping reactor" % (self.peer))
        self.stop_reactor()

    def on_message(self, message, binary):
        if not binary:
            msg = message.decode('utf-8')
            LOGGER.info(f"Received {msg}")
            if "MEDIA_START" in msg:
                ma = msg.split(" ")
                for p in ma[1:]:
                    v = p.split(":")
                    if v[0] == "channel":
                        chan_name = v[1]
                    elif v[0] == "optimal_frame_size":
                        self.optimal_frame_size = int(v[1])
                self.protocol.sendMessage(b"ANSWER", isBinary=False)

                """
                Don't tie up the reactor main thread with file I/O.
                """
                reactor.callInThread(self.protocol.sendFile,
                                     f"{TEST_DIR}/zombies.ulaw")
            if "MEDIA_XOFF" in msg:
                self.received_xoff = True
            if "MEDIA_XON" in msg:
                self.received_xon = True
                self.protocol.sendMessage(b"REPORT_QUEUE_DRAINED", isBinary=False)
                self.protocol.sendMessage(b"FLUSH_MEDIA", isBinary=False)
            if "QUEUE_DRAINED" in msg:
                self.protocol.sendClose(1000)
                self.passed = (self.received_xoff and self.received_xon)

