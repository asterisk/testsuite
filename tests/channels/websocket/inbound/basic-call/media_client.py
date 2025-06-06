#!/usr/bin/env python

"""A test that creates a media websocket client
   and checks that media echoed back matches what was sent.

NOTE:  There are TWO websockets at play here, one for ARI
and one for media.

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
from asterisk.media_websocket import MediaWebSocketClientFactory
from asterisk.ari import AriClientFactory

LOGGER = logging.getLogger(__name__)
USERPASS = ('testsuite', 'testsuite')

TEST_DIR = os.path.dirname(os.path.realpath(__file__))

class AriMediaClient(TestCase):
    def __init__(self, test_path='', test_config=None):
        super().__init__(test_path, test_config)

        if test_config is None:
            test_config = {}

        self.reactor_timeout = test_config.get('reactor-timeout', 10)
        LOGGER.info(f"Reactor timeout {self.reactor_timeout}")

        self.conn_id = None
        LOGGER.info("Registering startup observer")
        self.register_start_observer(self.on_startup)
        self.create_asterisk()

    def run(self):
        super().run()

    def on_startup(self, ast):
        LOGGER.info("Asterisk started")
        self.ast = ast
        self.passed = False
        """
        To prevent the complexity of having to create our own
        local channel and bridge, we will use the ARI client
        just to receive events so we'll set the apps to '*'
        and subscribe to all events. See on_ws_open() for
        more details.
        """
        self.ari_factory = AriClientFactory(receiver=self,
                                        host=self.ast[0].host,
                                        port=8088,
                                        apps='*',
                                        subscribe_all=True,
                                        userpass=USERPASS,
                                        timeout_secs=10)
        self.ari_factory.connect()

    def on_ws_open(self, protocol):
        LOGGER.info("WebSocket connection made: %s" % protocol)
        self.protocol = protocol
        """
        This is the easiest way to originate a call.
        We'll then watch for the dial event to get the
        connection id we'll need to connect to the media
        websocket.
        """
        self.ast[0].cli_exec("channel originate WebSocket/INCOMING/c(ulaw)n extension echo@default")

    def on_ws_event(self, message):
        msg_type = message.get('type')
        callback = getattr(self, 'handle_%s' % msg_type.lower(), None)
        if callback:
            callback(message)

    def on_reactor_timeout(self):
        self.protocol.sendClose(1000)

    def on_ws_closed(self, protocol):
        LOGGER.info("WebSocket connection closed")
        self.stop_reactor()

    def on_media_closed(self, result):
        LOGGER.info("Received notification that the media websocket closed")
        self.passed = result
        self.protocol.sendClose(1000)

    def handle_dial(self, message):
        chan_name = message['peer']['name']
        if message['dialstatus'] == "":
            self.conn_id = message['peer']['channelvars']['MEDIA_WEBSOCKET_CONNECTION_ID']
            self.media = ChanWebSocketTest(self.conn_id,
                        self.on_media_closed, self.reactor_timeout)
            self.media.run_test()

class ChanWebSocketTest(object):

    def __init__(self, conn_id, on_close, timeout=15):
        self.conn_id = conn_id
        self.timeout = timeout
        self.sent_buffer = None
        self.recvd_buffer = None
        self.optimal_frame_size = 0
        self.protocol = None
        self.on_close = on_close

        self.factory = MediaWebSocketClientFactory(
            self, f"ws://localhost:8088/media/{self.conn_id}",
            protocol="media", timeout_secs=timeout)
        """
        Setting autoFragmentSize to 500 will cause the
        payload sent to be split into chunks of 500 bytes
        sent with continuation frames.  This is useful
        for testing that chan_websocket can handle
        fragmented frames properly.
        """
        self.factory.setProtocolOptions(tcpNoDelay=True,
                                        autoFragmentSize=500)

    def run_test(self):
        self.factory.connect()

    def on_ws_open(self, protocol):
        LOGGER.info("Media WebSocket connection opened")
        self.protocol = protocol
        self.sent_buffer = io.BytesIO()
        self.recvd_buffer = io.BytesIO()

    def on_ws_closed(self, protocol):
        LOGGER.info("Media WebSocket connection closed")
        self.sent_buffer.close()
        self.recvd_buffer.close()

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
                                     f"{TEST_DIR}/test.ulaw",
                                     sent_buffer=self.sent_buffer)
            if "MEDIA_BUFFERING_COMPLETED" in msg:
                self.protocol.sendClose(1000)
                LOGGER.info(f"Checking buffers")
                if self.check_data() == 0:
                    self.on_close(True)
        else:
            self.recvd_buffer.write(message)

    def check_data(self):
        rc = 0
        sent_bytes = self.sent_buffer.getvalue()
        sent_length = len(sent_bytes)
        received_bytes = self.recvd_buffer.getvalue()
        received_length = len(received_bytes)

        """
        If the file we sent wasn't an even multiple of
        optimal_frame_size, the channel driver will have padded it
        with silence before sending it to the core.  This means
        that the amount of data we get back will be greater
        than what was sent by the amount needed to fill the
        short frame.
        """
        if (sent_length % self.optimal_frame_size) != 0:
            expected_length = sent_length + (self.optimal_frame_size - (sent_length % self.optimal_frame_size))
        else:
            expected_length = sent_length
        LOGGER.info(f"Bytes sent: {sent_length} Bytes expected: {expected_length} Bytes received: {received_length}")
        if received_length < expected_length:
            LOGGER.error("Bytes received < Bytes expected (failure)")
            return 1
        elif received_length > expected_length:
            LOGGER.info("Bytes received > Bytes expected (ok)")
        else:
            LOGGER.info("Bytes received == Bytes expected (ok)")

        """
        Since the received data may have been padded with silence,
        we only want to compare the first "sent_length" bytes in
        the received buffer.
        """
        if received_bytes[0:sent_length] != sent_bytes:
            LOGGER.error("Received buffer != sent buffer")
            return 1
        else:
            LOGGER.info("Received buffer == sent buffer")
            return 0

