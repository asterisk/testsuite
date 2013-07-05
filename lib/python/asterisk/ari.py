'''
Copyright (C) 2013, Digium, Inc.
David M. Lee, II <dlee@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import datetime
import json
import logging
import re
import requests
import time
import traceback
import urllib

from twisted.internet import reactor
from autobahn.websocket import WebSocketClientFactory, \
    WebSocketClientProtocol, connectWS

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8088


class WebSocketEventModule(object):
    '''Module for capturing events from the ARI WebSocket
    '''

    def __init__(self, module_config, test_object):
        '''Constructor.

        :param module_config: Configuration dict parse from test-config.yaml.
        :param test_object: Test control object.
        '''
        logger.debug("WebSocketEventModule(%r)", test_object)
        self.host = '127.0.0.1'
        self.port = DEFAULT_PORT
        self.test_object = test_object
        username = module_config.get('username') or 'testsuite'
        password = module_config.get('password') or 'testsuite'
        userpass = (username, password)
        #: ARI interface object
        self.ari = ARI(self.host, port=self.port, userpass=userpass)
        #: Matchers for incoming events
        self.event_matchers = [
            EventMatcher(self.ari, e, test_object)
            for e in module_config['events']]
        apps = module_config.get('apps') or 'testsuite'
        if isinstance(apps, list):
            apps = ','.join(apps)
        #: Twisted protocol factory for ARI WebSockets
        self.factory = AriClientFactory(host=self.host, port=self.port,
                                        apps=apps, on_event=self.on_event,
                                        userpass=userpass)

    def on_event(self, event):
        '''Handle incoming events from the WebSocket.

        :param event: Dictionary parsed from incoming JSON event.
        '''
        logger.error('%r' % event)
        for matcher in self.event_matchers:
            matcher.on_event(event)


class AriClientFactory(WebSocketClientFactory):
    '''Twisted protocol factory for building ARI WebSocket clients.
    '''
    def __init__(self, host, apps, on_event, userpass, port=DEFAULT_PORT,
                 timeout_secs=60):
        '''Constructor

        :param host: Hostname of Asterisk.
        :param apps: App names to subscribe to.
        :param on_event: Callback to invoke for all received events.
        :param port: Port of Asterisk web server.
        :param timeout_secs: Maximum time to try to connect to Asterisk.
        '''
        url = "ws://%s:%d/ari/events?%s" % \
              (host, port,
               urllib.urlencode({'app': apps, 'api_key': '%s:%s' % userpass}))
        logger.info("WebSocketClientFactory(url=%s)" % url)
        WebSocketClientFactory.__init__(self, url)
        self.on_event = on_event
        self.timeout_secs = timeout_secs
        self.protocol = self.__build_protocol
        self.attempts = 0
        self.start = None

        self.reconnect()

    def __build_protocol(self):
        '''Build a client protocol instance
        '''
        return AriClientProtocol(self.on_event)

    def clientConnectionFailed(self, connector, reason):
        '''Callback when client connection failed to connect.

        :param connector: Twisted connector.
        :param reason: Failure reason.
        '''
        logger.info("clientConnectionFailed(%s)" % (reason))
        reactor.callLater(1, self.reconnect)

    def reconnect(self):
        '''Attempt to reconnect the ARI WebSocket.

        This call will give up after timeout_secs has been exceeded.
        '''
        self.attempts += 1
        logger.debug("WebSocket attempt #%d" % self.attempts)
        if not self.start:
            self.start = datetime.datetime.now()
        runtime = (datetime.datetime.now() - self.start).seconds
        if runtime >= self.timeout_secs:
            logger.error("  Giving up after %d seconds" % self.timeout_secs)
            return

        connectWS(self)


class AriClientProtocol(WebSocketClientProtocol):
    '''Twisted protocol for handling a ARI WebSocket connection.
    '''
    def __init__(self, on_event):
        '''Constructor.

        :param on_event: Callback to invoke with each parsed event.
        '''
        self.on_event = on_event

    def onOpen(self):
        '''Called back when connection is open.
        '''
        logger.debug("onOpen()")

    def onClose(self, wasClean, code, reason):
        '''Called back when connection is closed.
        '''
        logger.debug("onClose(%r, %d, %s)" % (wasClean, code, reason))
        reactor.callLater(1, self.factory.reconnect)

    def onMessage(self, msg, binary):
        '''Called back when message is received.

        :param msg: Received text message.
        '''
        logger.info("rxed: %s" % msg)
        self.on_event(json.loads(msg))


class ARI(object):
    '''Bare bones object for an ARI interface.
    '''

    def __init__(self, host, userpass, port=DEFAULT_PORT):
        '''Constructor.

        :param host: Hostname of Asterisk.
        :param port: Port of the Asterisk webserver.
        '''
        self.base_url = "http://%s:%d/ari" % (host, port)
        self.userpass = userpass

    def build_url(self, *args):
        '''Build a URL from the given path.

        For example::
            # Builds the URL for /channels/{channel_id}/answer
            ari.build_url('channels', channel_id, 'answer')

        :param args: Path segments.
        '''
        path = [str(arg) for arg in args]
        return '/'.join([self.base_url] + path)

    def get(self, *args, **kwargs):
        '''Send a GET request to ARI.

        :param args: Path segements.
        :param kwargs: Query parameters.
        :returns: requests.models.Response
        :throws: requests.exceptions.HTTPError
        '''
        url = self.build_url(*args)
        logger.info("GET %s %r" % (url, kwargs))
        return raise_on_err(requests.get(url, params=kwargs, auth=self.userpass))

    def post(self, *args, **kwargs):
        '''Send a POST request to ARI.

        :param args: Path segements.
        :param kwargs: Query parameters.
        :returns: requests.models.Response
        :throws: requests.exceptions.HTTPError
        '''
        url = self.build_url(*args, **kwargs)
        logger.info("POST %s %r" % (url, kwargs))
        return raise_on_err(requests.post(url, params=kwargs, auth=self.userpass))

    def delete(self, *args, **kwargs):
        '''Send a DELETE request to ARI.

        :param args: Path segements.
        :param kwargs: Query parameters.
        :returns: requests.models.Response
        :throws: requests.exceptions.HTTPError
        '''
        url = self.build_url(*args, **kwargs)
        logger.info("DELETE %s %r" % (url, kwargs))
        return raise_on_err(requests.delete(url, params=kwargs, auth=self.userpass))


def raise_on_err(resp):
    '''Helper to raise an exception when a response is a 4xx or 5xx error.

    :param resp: requests.models.Response object
    :returns: resp
    '''
    resp.raise_for_status()
    return resp


class EventMatcher(object):
    '''Object to observe incoming events and match them agains a configuration.
    '''
    def __init__(self, ari, instance_config, test_object):
        self.ari = ari
        self.instance_config = instance_config
        self.test_object = test_object
        self.conditions = self.instance_config['conditions']
        self.count_range = decode_range(self.instance_config.get('count'))
        self.count = 0
        self.passed = True
        callback = self.instance_config.get('callback')
        if callback:
            module = __import__(callback['module'])
            self.callback = getattr(module, callback['method'])
        else:
            # No callback; just use a no-op
            self.callback = lambda **kwargs: None

        test_object.register_stop_observer(self.on_stop)

    def on_event(self, message):
        '''Callback for every received ARI event.

        :param message: Parsed event from ARI WebSocket.
        '''
        if self.matches(message):
            self.count += 1
            # Split call and accumulation to always call the callback
            try:
                res = self.callback(self.ari, message)
                if not res:
                    logger.error("Callback failed: %r" %
                                 self.instance_config)
                    self.passed = False
            except:
                logger.error("Exception in callback: %s" %
                             traceback.format_exc())
                self.passed = False

    def on_stop(self, *args):
        '''Callback for the end of the test.

        :param args: Ignored arguments.
        '''
        if not self.count_range.contains(self.count):
            logger.error("Expected %d <= count <= %d; was %d (%r)",
                         self.count_range.min, self.count_range.max,
                         self.count, self.conditions)
            self.passed = False
        self.test_object.set_passed(self.passed)

    def matches(self, message):
        '''Compares a message against the configured conditions.

        :param message: Incoming ARI WebSocket event.
        :returns: True if message matches conditions; False otherwise.
        '''
        match = self.conditions.get('match')
        res = all_match(match, message)

        # Now validate the nomatch, if it's there
        nomatch = self.conditions.get('nomatch')
        if res and nomatch:
            res = not all_match(nomatch, message)
        return res


def all_match(pattern, message):
    '''Match a pattern from the YAML config with a received message.

    :param pattern: Configured pattern.
    :param message: Message to compare.
    :returns: True if message matches pattern; False otherwise.
    '''
    #logger.debug("%r ?= %r" % (pattern, message))
    #logger.debug("  %r" % type(pattern))
    #logger.debug("  %r" % type(message))
    if pattern is None:
        # Empty pattern always matches
        return True
    elif isinstance(pattern, list):
        # List must be an exact match
        res = len(pattern) == len(message)
        i = 0
        while res and i < len(pattern):
            res = all_match(pattern[i], message[i])
            i += 1
        return res
    elif isinstance(pattern, dict):
        # Dict should match for every field in the pattern.
        # extra fields in the message are fine.
        for key, value in pattern.iteritems():
            to_check = message.get(key)
            if to_check is None or not all_match(value, to_check):
                return False
        return True
    elif isinstance(pattern, str) or isinstance(pattern, unicode):
        # Pattern strings are considered to be regexes
        return re.match(pattern, message) is not None
    elif isinstance(pattern, int):
        # Integers are literal matches
        return pattern == message
    else:
        logger.error("Unhandled pattern type %s" % type(pattern)).__name__


class Range(object):
    '''Utility object to handle numeric ranges (inclusive).
    '''
    def __init__(self, min=0, max=float("inf")):
        '''Constructor.

        :param min: Minimum value of the range.
        :param max: Maximum value of the range.
        '''
        self.min = min
        self.max = max

    def contains(self, v):
        '''Checks if the given value is within this Range.

        :param v: Value to check.
        :returns: True/False if v is/isn't in the Range.
        '''
        return self.min <= v <= self.max


def decode_range(yaml):
    '''Parse a range from YAML specification.
    '''
    if yaml is None:
        # Unspecified; receive at least one
        return Range(1, float("inf"))
    elif isinstance(yaml, int):
        # Need exactly this many events
        return Range(yaml, yaml)
    elif yaml[0] == '<':
        # Need at most this many events
        return Range(0, int(yaml[1:]))
    elif yaml[0] == '>':
        # Need at least this many events
        return Range(int(yaml[1:]), float("inf"))
    else:
        # Need exactly this many events
        return Range(int(yaml), int(yaml))
