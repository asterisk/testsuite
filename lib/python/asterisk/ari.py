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
import traceback
import urllib

from TestCase import TestCase
from twisted.internet import reactor
from autobahn.websocket import WebSocketClientFactory, \
    WebSocketClientProtocol, connectWS

LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 8088

#: Default matcher to ensure we don't have any validation failures on the
#  WebSocket
VALIDATION_MATCHER = {
    'conditions': {
        'match': {
            'error': "^InvalidMessage$"
        }
    },
    'count': 0
}


class AriTestObject(TestCase):
    ''' Class that acts as a Test Object in the pluggable module framework '''

    def __init__(self, test_path='', test_config=None):
        ''' Constructor for a test object

        Keyword Arguments:
        test_path The full path to the test location
        test_config The YAML test configuration
        '''
        super(AriTestObject, self).__init__(test_path, test_config)

        if test_config is None:
            # Meh, just use defaults
            test_config = {}

        self.apps = test_config.get('apps') or 'testsuite'
        if isinstance(self.apps, list):
            self.apps = ','.join(self.apps)
        host = test_config.get('host') or '127.0.0.1'
        port = test_config.get('port') or DEFAULT_PORT
        userpass = (test_config.get('username') or 'testsuite',
            test_config.get('password') or 'testsuite')

        # Create the REST interface and the WebSocket Factory
        self.ari = ARI(host, port=port, userpass=userpass)
        self.ari_factory = AriClientFactory(receiver=self, host=host, port=port,
                                        apps=self.apps,
                                        userpass=userpass)
        self.iterations = test_config.get('test-iterations')

        self.test_iteration = 0
        self.channels = []
        self._ws_event_handlers = []
        self.timed_out = False

        if self.iterations is None:
            self.iterations = [{'channel': 'Local/s@default',
                'application': 'Echo'}]

        self.create_asterisk(count=1)

    def run(self):
        ''' Override of TestCase run

        Called when reactor starts and after all instances of Asterisk have started
        '''
        super(AriTestObject, self).run()
        self.ari_factory.connect()

    def register_ws_event_handler(self, callback):
        ''' Register a callback for when an event is received over the WS

        :param callback The method to call when an event is received. This
        will have a single parameter (the event) passed to it
        '''
        self._ws_event_handlers.append(callback)

    def on_reactor_timeout(self):
        self.timed_out = True
        # Fail the tests if we have timed out
        self.set_passed(False)

    def on_ws_event(self, message):
        ''' Handler for WebSocket events

        :param message The WS event payload
        '''
        if self.timed_out:
            # Ignore messages received after timeout
            LOGGER.debug("Ignoring message received after timeout")
            return

        for handler in self._ws_event_handlers:
            handler(message)

    def on_ws_open(self, protocol):
        ''' Handler for WebSocket Client Protocol opened

        :param protocol The WS Client protocol object
        '''
        reactor.callLater(0, self._create_ami_connection)

    def on_ws_closed(self, protocol):
        ''' Handler for WebSocket Client Protocol closed

        :param protocol The WS Client protocol object
        '''
        LOGGER.debug('WebSocket connection closed...')

    def _create_ami_connection(self):
        ''' Create the AMI connection '''
        self.create_ami_factory(count=1)

    def ami_connect(self, ami):
        ''' Override of TestCase ami_connect
        Called when an AMI connection is made

        :param ami The AMI factory
        '''
        ami.registerEvent('Newchannel', self._new_channel_handler)
        ami.registerEvent('Hangup', self._hangup_handler)
        self.execute_test()

    def _new_channel_handler(self, ami, event):
        ''' Handler for new channels

        :param ami The AMI instance
        :param event The Newchannl event
        '''
        LOGGER.debug('Tracking channel %s' % event['channel'])
        self.channels.append(event['channel'])

    def _hangup_handler(self, ami, event):
        ''' Handler for channel hangup

        :param ami The AMI instance
        :param event Hangup event
        '''
        LOGGER.debug('Removing tracking for %s' % event['channel'])
        self.channels.remove(event['channel'])
        if len(self.channels) == 0:
            self.test_iteration += 1
            self.execute_test()

    def execute_test(self):
        ''' Execute the current iteration of the test '''

        if (self.test_iteration == len(self.iterations)):
            LOGGER.info('All iterations executed; stopping')
            self.stop_reactor()
            return

        iteration = self.iterations[self.test_iteration]
        if isinstance(iteration, list):
            for channel in iteration:
                self._spawn_channel(channel)
        else:
            self._spawn_channel(iteration)

    def _spawn_channel(self, channel_def):
        ''' Create a new channel '''

        # There's only one Asterisk instance, so just use the first AMI factory
        LOGGER.info('Creating channel %s' % channel_def['channel'])
        self.ami[0].originate(**channel_def).addErrback(self.handleOriginateFailure)


class WebSocketEventModule(object):
    '''Module for capturing events from the ARI WebSocket
    '''

    def __init__(self, module_config, test_object):
        '''Constructor.

        :param module_config: Configuration dict parse from test-config.yaml.
        :param test_object: Test control object.
        '''
        self.ari = test_object.ari
        self.event_matchers = [
            EventMatcher(self.ari, e, test_object)
            for e in module_config['events']]
        self.event_matchers.append(EventMatcher(self.ari, VALIDATION_MATCHER,
                                                test_object))
        test_object.register_ws_event_handler(self.on_event)

    def on_event(self, event):
        '''Handle incoming events from the WebSocket.

        :param event: Dictionary parsed from incoming JSON event.
        '''
        LOGGER.debug('Received event: %r' % event.get('type'))
        matched = False
        for matcher in self.event_matchers:
            if matcher.on_event(event):
                matched = True
        if not matched:
            LOGGER.info('Event had no matcher: %r' % event)


class AriClientFactory(WebSocketClientFactory):
    '''Twisted protocol factory for building ARI WebSocket clients.
    '''
    def __init__(self, receiver, host, apps, userpass, port=DEFAULT_PORT,
        timeout_secs=60):
        '''Constructor

        :param receiver The object that will receive events from the protocol
        :param host: Hostname of Asterisk.
        :param apps: App names to subscribe to.
        :param port: Port of Asterisk web server.
        :param timeout_secs: Maximum time to try to connect to Asterisk.
        '''
        url = "ws://%s:%d/ari/events?%s" % \
              (host, port,
               urllib.urlencode({'app': apps, 'api_key': '%s:%s' % userpass}))
        LOGGER.info("WebSocketClientFactory(url=%s)" % url)
        WebSocketClientFactory.__init__(self, url, debug = True,
            protocols=['ari'])
        self.timeout_secs = timeout_secs
        self.attempts = 0
        self.start = None
        self.receiver = receiver

    def buildProtocol(self, addr):
        ''' Make the protocol '''
        return AriClientProtocol(self.receiver, self)

    def clientConnectionFailed(self, connector, reason):
        ''' Doh, connection lost '''
        LOGGER.debug('Connection lost; attempting again in 1 second')
        reactor.callLater(1, self.reconnect)

    def connect(self):
        ''' Start the connection '''
        self.reconnect()

    def reconnect(self):
        '''Attempt to reconnect the ARI WebSocket.

        This call will give up after timeout_secs has been exceeded.
        '''
        self.attempts += 1
        LOGGER.debug("WebSocket attempt #%d" % self.attempts)
        if not self.start:
            self.start = datetime.datetime.now()
        runtime = (datetime.datetime.now() - self.start).seconds
        if runtime >= self.timeout_secs:
            LOGGER.error("  Giving up after %d seconds" % self.timeout_secs)
            raise Exception("Failed to connect after %d seconds" % self.timeout_secs)

        connectWS(self)


class AriClientProtocol(WebSocketClientProtocol):
    '''Twisted protocol for handling a ARI WebSocket connection.
    '''
    def __init__(self, receiver, factory):
        '''Constructor.

        :param receiver The event receiver
        '''
        LOGGER.debug('Made me a client protocol!')
        self.receiver = receiver
        self.factory = factory

    def onOpen(self):
        '''Called back when connection is open.
        '''
        LOGGER.debug('WebSocket Open')
        self.receiver.on_ws_open(self)

    def onClose(self, wasClean, code, reason):
        '''Called back when connection is closed.
        '''
        LOGGER.debug("WebSocket closed(%r, %d, %s)" % (wasClean, code, reason))
        self.receiver.on_ws_closed(self)

    def onMessage(self, msg, binary):
        '''Called back when message is received.

        :param msg: Received text message.
        '''
        LOGGER.debug("rxed: %s" % msg)
        msg = json.loads(msg)
        self.receiver.on_ws_event(msg)


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
        self.allow_errors = False

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
        LOGGER.info("GET %s %r" % (url, kwargs))
        return self.raise_on_err(requests.get(url, params=kwargs,
                                         auth=self.userpass))

    def post(self, *args, **kwargs):
        '''Send a POST request to ARI.

        :param args: Path segements.
        :param kwargs: Query parameters.
        :returns: requests.models.Response
        :throws: requests.exceptions.HTTPError
        '''
        url = self.build_url(*args)
        LOGGER.info("POST %s %r" % (url, kwargs))
        return self.raise_on_err(requests.post(url, params=kwargs,
                                          auth=self.userpass))

    def delete(self, *args, **kwargs):
        '''Send a DELETE request to ARI.

        :param args: Path segements.
        :param kwargs: Query parameters.
        :returns: requests.models.Response
        :throws: requests.exceptions.HTTPError
        '''
        url = self.build_url(*args)
        LOGGER.info("DELETE %s %r" % (url, kwargs))
        return self.raise_on_err(requests.delete(url, params=kwargs,
                                            auth=self.userpass))

    def set_allow_errors(self, v):
        '''Sets whether error responses returns exceptions.

        If True, then error responses are returned. Otherwise, methods throw
        an exception on error.

        :param v True/False value for allow_errors.
        '''
        self.allow_errors = v

    def raise_on_err(self, resp):
        '''Helper to raise an exception when a response is a 4xx or 5xx error.

        If allow_errors is True, then an exception is not raised.

        :param resp: requests.models.Response object
        :returns: resp
        '''
        if not self.allow_errors and resp.status_code / 100 != 2:
            LOGGER.error('%s (%d %s): %r' % (resp.url, resp.status_code, resp.reason, resp.text))
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
            self.callback = lambda *args, **kwargs: True

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
                if res:
                    return True
                else:
                    LOGGER.error("Callback failed: %r" %
                                 self.instance_config)
                    self.passed = False
            except:
                LOGGER.error("Exception in callback: %s" %
                             traceback.format_exc())
                self.passed = False
        return False

    def on_stop(self, *args):
        '''Callback for the end of the test.

        :param args: Ignored arguments.
        '''
        if not self.count_range.contains(self.count):
            # max could be int or float('inf'); format with %r
            LOGGER.error("Expected %d <= count <= %r; was %d (%r)",
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
    #LOGGER.debug("%r ?= %r" % (pattern, message))
    #LOGGER.debug("  %r" % type(pattern))
    #LOGGER.debug("  %r" % type(message))
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
        LOGGER.error("Unhandled pattern type %s" % type(pattern)).__name__


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
