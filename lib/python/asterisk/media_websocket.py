"""
Copyright (C) 2025, Sangoma Technologies Corporation
George T Joseph <gjoseph@sangoma.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import datetime
import logging
import io

from twisted.internet import reactor
from autobahn.twisted.websocket import WebSocketClientFactory, \
    WebSocketClientProtocol, connectWS, WebSocketServerFactory, \
    WebSocketServerProtocol

LOGGER = logging.getLogger(__name__)

class MediaWebSocketMixin:
    def has_function(self, func):
        return hasattr(self.receiver, func) \
            and callable(getattr(self.receiver, func))

    def onConnect(self, request):
        LOGGER.debug("New WebSocket Connected")
        if self.has_function("on_ws_connect"):
            self.receiver.on_ws_connect(request)

    def onOpen(self):
        LOGGER.debug("WebSocket Open")
        if self.has_function("on_ws_open"):
            self.receiver.on_ws_open(self)

    def onClose(self, wasClean, code, reason):
        LOGGER.debug(f"WebSocket closed({wasClean}, {code}, {reason})")
        if self.has_function("on_ws_closed"):
            self.receiver.on_ws_closed(self)

    def onMessage(self, msg, binary):
        if self.has_function("on_message"):
            self.receiver.on_message(msg, binary)

    def sendFile(self, filename, sent_buffer=None):
        buff_size = 1000
        f = io.open(filename, "rb", buffering=0)
        LOGGER.info(f"Playing '{filename}'")
        self.sendMessage(b"START_MEDIA_BUFFERING", isBinary=False)
        while True:
            buff = f.read(buff_size)
            if buff is None or len(buff) <= 0:
                break
            # Send on the websocket
            self.sendMessage(buff, isBinary=True)
            if sent_buffer is not None:
            # Save in buffer so we can compare to what was received.
                sent_buffer.write(buff)
        f.close()
        self.sendMessage(b"STOP_MEDIA_BUFFERING", isBinary=False)
        LOGGER.info(f"Stopping '{filename}'")

class MediaWebSocketClientFactory(WebSocketClientFactory):
    """Twisted protocol factory for building Media WebSocket clients."""

    def __init__(self, receiver, uri, protocol="media", timeout_secs=60):
        """Constructor

        :param receiver The object that will receive events from the protocol
        :param uri The websocket server URI
        :param timeout_secs: Maximum time to try to connect to Asterisk.
        """
        LOGGER.info(f"WebSocketClientFactory(uri={uri})")
        super().__init__(uri, protocols=[protocol])
        self.timeout_secs = timeout_secs
        self.attempts = 0
        self.start = None
        self.receiver = receiver

    def buildProtocol(self, addr):
        return MediaWebSocketClientProtocol(self.receiver, self)

    def clientConnectionFailed(self, connector, reason):
        LOGGER.debug("Connection lost; attempting again in 1 second")
        reactor.callLater(1, self.reconnect)

    def connect(self):
        self.reconnect()

    def reconnect(self):
        self.attempts += 1
        LOGGER.debug(f"WebSocket attempt #{self.attempts}")
        if not self.start:
            self.start = datetime.datetime.now()
        runtime = (datetime.datetime.now() - self.start).seconds
        if runtime >= self.timeout_secs:
            LOGGER.error(f"  Giving up after {self.timeout_secs} seconds")
            raise Exception(f"Failed to connect after {self.timeout_secs} seconds")

        connectWS(self)

class MediaWebSocketClientProtocol(MediaWebSocketMixin, WebSocketClientProtocol):
    """Twisted protocol for handling a Media WebSocket client connection."""

    def __init__(self, receiver, factory):
        """Constructor.

        :param receiver The event receiver
        :param factory The factory creating this protocol
        """
        WebSocketClientProtocol.__init__(self)
        self.receiver = receiver
        self.factory = factory


class MediaWebSocketServerFactory(WebSocketServerFactory):
    """Twisted protocol factory for building Media WebSocket clients."""

    def __init__(self, receiver, uri, server_name, protocols=['media']):
        """Constructor

        :param receiver The object that will receive events from the protocol
        :param uri URI to be served.
        :param server_name server name for HTTP response.
        :param protocols List of protocols to accept.
        """
        super().__init__(uri, protocols, server_name)
        self.attempts = 0
        self.start = None
        self.receiver = receiver

    def buildProtocol(self, addr):
        return MediaWebSocketServerProtocol(self.receiver, self)

class MediaWebSocketServerProtocol(MediaWebSocketMixin, WebSocketServerProtocol):
    """Twisted protocol for handling a Media WebSocket server connection."""

    def __init__(self, receiver, factory):
        """Constructor.

        :param receiver The event receiver
        :param factory The factory creating this protocol
        """
        WebSocketServerProtocol.__init__(self)
        self.receiver = receiver
        self.factory = factory

