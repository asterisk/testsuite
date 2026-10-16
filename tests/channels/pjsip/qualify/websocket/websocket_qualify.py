"""Verify qualification reuses a registered contact's WebSocket connection.

Copyright (C) 2026, Sangoma Technologies Corporation
This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging

from autobahn.twisted.websocket import (
    WebSocketClientFactory, WebSocketClientProtocol, connectWS)

LOGGER = logging.getLogger(__name__)


class SIPProtocol(WebSocketClientProtocol):
    """A browser-style SIP client that registers and answers OPTIONS."""

    def onOpen(self):
        self.factory.test.protocol = self
        self.sendMessage((
            'REGISTER sip:127.0.0.1 SIP/2.0\r\n'
            'Via: SIP/2.0/WS browser.invalid;branch=z9hG4bKregister\r\n'
            'From: <sip:browser@127.0.0.1>;tag=browser\r\n'
            'To: <sip:browser@127.0.0.1>\r\n'
            'Call-ID: websocket-qualify-register\r\n'
            'CSeq: 1 REGISTER\r\n'
            'Contact: <sip:browser@browser.invalid;transport=ws>\r\n'
            'Expires: 60\r\n'
            'Max-Forwards: 70\r\n'
            'Content-Length: 0\r\n\r\n').encode('utf-8'))

    def onMessage(self, payload, isBinary):
        message = payload.decode('utf-8')
        LOGGER.debug('Received SIP over WebSocket: %s', message)
        if message.startswith('SIP/2.0 200'):
            self.factory.test.registered = True
        elif message.startswith('OPTIONS '):
            headers = []
            for line in message.split('\r\n')[1:]:
                name = line.partition(':')[0].lower()
                if name in ('via', 'from', 'to', 'call-id', 'cseq'):
                    if name == 'to':
                        line += ';tag=browser'
                    headers.append(line)
            response = ('SIP/2.0 200 OK\r\n' + '\r\n'.join(headers)
                        + '\r\nContent-Length: 0\r\n\r\n')
            self.sendMessage(response.encode('utf-8'))
            self.factory.test.answered = True
        else:
            self.factory.test.fail('Unexpected SIP message: %s' % message)

    def onClose(self, wasClean, code, reason):
        self.factory.test.fail('WebSocket closed: %s' % reason)


class SIPFactory(WebSocketClientFactory):
    protocol = SIPProtocol

    def clientConnectionFailed(self, connector, reason):
        self.test.fail('WebSocket connection failed: %s' % reason)


class WebSocketQualify:
    """Pass only after an answered OPTIONS makes the contact Reachable."""

    def __init__(self, config, test_object):
        self.test_object = test_object
        self.protocol = None
        self.registered = False
        self.answered = False
        self.stopping = False
        test_object.register_ami_observer(self.ami_connected)
        test_object.register_stop_observer(self.stop)

    def ami_connected(self, ami):
        ami.registerEvent('ContactStatus', self.contact_status)
        factory = SIPFactory('ws://127.0.0.1:8088/ws', protocols=['sip'])
        factory.test = self
        self.connector = connectWS(factory)

    def contact_status(self, ami, event):
        if event.get('aor') != 'browser':
            return
        # A newly registered contact may be published before its first qualify.
        if event.get('contactstatus') == 'NonQualified':
            return
        if event.get('contactstatus') != 'Reachable':
            self.fail('Contact failed qualification: %s' % event)
            return
        if not self.registered or not self.answered:
            self.fail('Contact became Reachable without registration and OPTIONS')
            return
        self.stopping = True
        self.test_object.set_passed(True)
        self.test_object.stop_reactor()

    def fail(self, reason):
        if self.stopping:
            return
        LOGGER.error(reason)
        self.stopping = True
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()

    def stop(self, result):
        self.stopping = True
        if self.protocol:
            self.protocol.sendClose()
        if hasattr(self, 'connector'):
            self.connector.disconnect()
        return result
