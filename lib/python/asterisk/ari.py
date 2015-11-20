"""
Copyright (C) 2013, Digium, Inc.
David M. Lee, II <dlee@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import datetime
import json
import logging
import re
import requests
import traceback
import urllib

from test_case import TestCase
from pluggable_registry import PLUGGABLE_EVENT_REGISTRY,\
    PLUGGABLE_ACTION_REGISTRY, var_replace
from test_suite_utils import all_match
from twisted.internet import reactor
try:
    from autobahn.websocket import WebSocketClientFactory, \
        WebSocketClientProtocol, connectWS
except:
    from autobahn.twisted.websocket import WebSocketClientFactory, \
        WebSocketClientProtocol, connectWS

LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = '127.0.0.1'
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


class AriBaseTestObject(TestCase):
    """Class that acts as a Test Object in the pluggable module framework"""

    def __init__(self, test_path='', test_config=None):
        """Constructor for a test object

        :param test_path The full path to the test location
        :param test_config The YAML test configuration
        """
        super(AriBaseTestObject, self).__init__(test_path, test_config)

        if test_config is None:
            # Meh, just use defaults
            test_config = {}

        self.apps = test_config.get('apps', 'testsuite')
        if isinstance(self.apps, list):
            self.apps = ','.join(self.apps)
        default_host = DEFAULT_HOST
        if self.global_config.config:
            asterisks = self.global_config.config.get('asterisk-instances')
            if asterisks:
                default_host = asterisks[0]['host']
        host = test_config.get('host', default_host)
        port = test_config.get('port', DEFAULT_PORT)
        userpass = (test_config.get('username', 'testsuite'),
                    test_config.get('password', 'testsuite'))
        subscribe_all = test_config.get('subscribe-all')

        # Create the REST interface and the WebSocket Factory
        self.ari = ARI(host, port=port, userpass=userpass)
        self.ari_factory = AriClientFactory(receiver=self, host=host, port=port,
                                            apps=self.apps, userpass=userpass,
                                            subscribe_all=subscribe_all)

        self._ws_connection = None
        self._ws_event_handlers = []
        self._ws_open_handlers = []
        self.timed_out = False

        self.asterisk_instances = test_config.get('asterisk-instances', 1)
        self.create_asterisk(count=self.asterisk_instances)

    def run(self):
        """Override of TestCase run

        Called when reactor starts and after all instances of Asterisk have
        started
        """
        super(AriBaseTestObject, self).run()
        self.ari_factory.connect()

    def register_ws_event_handler(self, callback):
        """Register a callback for when an event is received over the WS

        :param callback The method to call when an event is received. This
        will have a single parameter (the event) passed to it
        """
        self._ws_event_handlers.append(callback)

    def on_reactor_timeout(self):
        """Called when the reactor times out"""
        self.timed_out = True
        # Fail the tests if we have timed out
        self.set_passed(False)

    def on_ws_event(self, message):
        """Handler for WebSocket events

        :param message The WS event payload
        """
        if self.timed_out:
            # Ignore messages received after timeout
            LOGGER.debug("Ignoring message received after timeout")
            return

        for handler in self._ws_event_handlers:
            handler(message)

    def on_ws_open(self, protocol):
        """Handler for WebSocket Client Protocol opened

        :param protocol The WS Client protocol object
        """
        self._ws_connection = protocol
        for observer in self._ws_open_handlers:
            observer(self)
        reactor.callLater(0, self._create_ami_connection)

    def register_ari_observer(self, observer):
        """Register an observer for ARI WS connection

        :param observer The WS observer. This will be called with this object.
        """
        self._ws_open_handlers.append(observer)

    def on_ws_closed(self, protocol):
        """Handler for WebSocket Client Protocol closed

        :param protocol The WS Client protocol object
        """
        self._ws_connection = None
        LOGGER.debug("WebSocket connection closed...")

    def _create_ami_connection(self):
        """Create the AMI connection"""
        self.create_ami_factory(count=self.asterisk_instances)

    def stop_reactor(self):
        if self._ws_connection is not None:
            self._ws_connection.dropConnection()
        super(AriBaseTestObject, self).stop_reactor()


class AriTestObject(AriBaseTestObject):
    """Class that acts as a Test Object in the pluggable module framework"""

    def __init__(self, test_path='', test_config=None):
        """Constructor for a test object

        :param test_path The full path to the test location
        :param test_config The YAML test configuration
        """
        super(AriTestObject, self).__init__(test_path, test_config)

        if test_config is None:
            # Meh, just use defaults
            test_config = {}

        self.iterations = test_config.get('test-iterations')
        self.stop_on_end = test_config.get('stop-on-end', True)
        self.test_iteration = 0
        self.channels = []

        if self.iterations is None:
            self.iterations = [{'channel': 'Local/s@default',
                                'application': 'Echo'}]

    def ami_connect(self, ami):
        """Override of AriBaseTestObject ami_connect
        Called when an AMI connection is made

        :param ami The AMI factory
        """
        # only use the first ami instance
        if ami.id != 0:
            return

        ami.registerEvent('Newchannel', self._new_channel_handler)
        ami.registerEvent('Hangup', self._hangup_handler)
        self.execute_test()
        return ami

    def _new_channel_handler(self, ami, event):
        """Handler for new channels

        :param ami The AMI instance
        :param event The Newchannl event
        """
        LOGGER.debug("Tracking channel %s", event['channel'])
        self.channels.append(event['channel'])
        return (ami, event)

    def _hangup_handler(self, ami, event):
        """Handler for channel hangup

        :param ami The AMI instance
        :param event Hangup event
        """
        if event['channel'] not in self.channels:
            return (ami, event)

        LOGGER.debug("Removing tracking for %s", event['channel'])
        self.channels.remove(event['channel'])
        if len(self.channels) == 0:
            self.test_iteration += 1
            self.execute_test()
        return (ami, event)

    def execute_test(self):
        """Execute the current iteration of the test"""

        if not isinstance(self.iterations, list):
            return

        if self.test_iteration == len(self.iterations):
            LOGGER.info("All iterations executed")
            if self.stop_on_end:
                LOGGER.info("Stopping test")
                self.stop_reactor()
            return

        iteration = self.iterations[self.test_iteration]
        if isinstance(iteration, list):
            for channel in iteration:
                self._spawn_channel(channel)
        else:
            self._spawn_channel(iteration)

    def _spawn_channel(self, channel_def):
        """Create a new channel"""

        # There's only one Asterisk instance, so just use the first AMI factory
        LOGGER.info("Creating channel %s", channel_def['channel'])
        if not self.ami[0]:
            LOGGER.warning("Error creating channel - no ami available")
            return
        deferred = self.ami[0].originate(**channel_def)
        deferred.addErrback(self.handle_originate_failure)


class AriOriginateTestObject(AriTestObject):
    """Class that overrides AriTestObject origination to use ARI"""

    def __init__(self, test_path='', test_config=None):
        """Constructor for a test object

        :param test_path The full path to the test location
        :param test_config The YAML test configuration
        """

        if test_config is None:
            test_config = {}

        if not test_config.get('test-iterations'):
            # preset the default test in ARI format to prevent post failure
            test_config['test-iterations'] = [{
                'endpoint': 'Local/s@default',
                'channelId': 'testsuite-default-id',
                'app': 'testsuite'
            }]

        super(AriOriginateTestObject, self).__init__(test_path, test_config)

    def _spawn_channel(self, channel_def):
        """Create a new channel"""

        # Create a channel using ARI POST to channel instead
        LOGGER.info("Creating channel %s", channel_def['endpoint'])
        self.ari.post('channels', **channel_def)


class WebSocketEventModule(object):
    """Module for capturing events from the ARI WebSocket"""

    def __init__(self, module_config, test_object):
        """Constructor.

        :param module_config: Configuration dict parse from test-config.yaml.
        :param test_object: Test control object.
        """
        self.ari = test_object.ari
        self.event_matchers = [
            EventMatcher(self.ari, e, test_object)
            for e in module_config['events']]
        self.event_matchers.append(EventMatcher(self.ari, VALIDATION_MATCHER,
                                                test_object))
        test_object.register_ws_event_handler(self.on_event)

    def on_event(self, event):
        """Handle incoming events from the WebSocket.

        :param event: Dictionary parsed from incoming JSON event.
        """
        LOGGER.debug("Received event: %r", event.get('type'))
        matched = False
        for matcher in self.event_matchers:
            if matcher.on_event(event):
                matched = True
        if not matched:
            LOGGER.info("Event had no matcher: %r", event)


class AriClientFactory(WebSocketClientFactory):
    """Twisted protocol factory for building ARI WebSocket clients."""

    def __init__(self, receiver, host, apps, userpass, port=DEFAULT_PORT,
                 timeout_secs=60, subscribe_all=False):
        """Constructor

        :param receiver The object that will receive events from the protocol
        :param host: Hostname of Asterisk.
        :param apps: App names to subscribe to.
        :param port: Port of Asterisk web server.
        :param timeout_secs: Maximum time to try to connect to Asterisk.
        :param subscribe_all: If true, subscribe to all events.
        """
        url = "ws://%s:%d/ari/events?%s" % \
              (host, port,
               urllib.urlencode({'app': apps, 'api_key': '%s:%s' % userpass}))
        if subscribe_all:
            url += '&subscribeAll=true'
        LOGGER.info("WebSocketClientFactory(url=%s)", url)
        WebSocketClientFactory.__init__(self, url, debug=True,
                                        protocols=['ari'], debugCodePaths=True)
        self.timeout_secs = timeout_secs
        self.attempts = 0
        self.start = None
        self.receiver = receiver

    def buildProtocol(self, addr):
        """Make the protocol"""
        return AriClientProtocol(self.receiver, self)

    def clientConnectionFailed(self, connector, reason):
        """Doh, connection lost"""
        LOGGER.debug("Connection lost; attempting again in 1 second")
        reactor.callLater(1, self.reconnect)

    def connect(self):
        """Start the connection"""
        self.reconnect()

    def reconnect(self):
        """Attempt to reconnect the ARI WebSocket.

        This call will give up after timeout_secs has been exceeded.
        """
        self.attempts += 1
        LOGGER.debug("WebSocket attempt #%d", self.attempts)
        if not self.start:
            self.start = datetime.datetime.now()
        runtime = (datetime.datetime.now() - self.start).seconds
        if runtime >= self.timeout_secs:
            LOGGER.error("  Giving up after %d seconds", self.timeout_secs)
            raise Exception("Failed to connect after %d seconds" %
                            self.timeout_secs)

        connectWS(self)


class AriClientProtocol(WebSocketClientProtocol):
    """Twisted protocol for handling a ARI WebSocket connection."""

    def __init__(self, receiver, factory):
        """Constructor.

        :param receiver The event receiver
        """
        try:
            super(AriClientProtocol, self).__init__()
        except TypeError as te:
            # Older versions of Autobahn use old style classes with no initializer.
            # Newer versions must have their initializer called by derived
            # implementations.
            LOGGER.debug("AriClientProtocol: TypeError thrown in init: {0}".format(te))
        LOGGER.debug("Made me a client protocol!")
        self.receiver = receiver
        self.factory = factory

    def onOpen(self):
        """Called back when connection is open."""
        LOGGER.debug("WebSocket Open")
        self.receiver.on_ws_open(self)

    def onClose(self, wasClean, code, reason):
        """Called back when connection is closed."""
        LOGGER.debug("WebSocket closed(%r, %d, %s)", wasClean, code, reason)
        self.receiver.on_ws_closed(self)

    def onMessage(self, msg, binary):
        """Called back when message is received.

        :param msg: Received text message.
        """
        LOGGER.debug("rxed: %s", msg)
        msg = json.loads(msg)
        self.receiver.on_ws_event(msg)


class ARI(object):
    """Bare bones object for an ARI interface."""

    def __init__(self, host, userpass, port=DEFAULT_PORT):
        """Constructor.

        :param host: Hostname of Asterisk.
        :param port: Port of the Asterisk webserver.
        """
        self.base_url = "http://%s:%d/ari" % (host, port)
        self.userpass = userpass
        self.allow_errors = False

    def build_url(self, *args):
        """Build a URL from the given path.

        For example::
            # Builds the URL for /channels/{channel_id}/answer
            ari.build_url('channels', channel_id, 'answer')

        :param args: Path segments.
        """
        path = [str(arg) for arg in args]
        return '/'.join([self.base_url] + path)

    def get(self, *args, **kwargs):
        """Send a GET request to ARI.

        :param args: Path segements.
        :param kwargs: Query parameters.
        :returns: requests.models.Response
        :throws: requests.exceptions.HTTPError
        """
        url = self.build_url(*args)
        LOGGER.info("GET %s %r", url, kwargs)
        return self.raise_on_err(requests.get(url, params=kwargs,
                                              auth=self.userpass))

    def put(self, *args, **kwargs):
        """Send a PUT request to ARI.

        :param args: Path segements.
        :param kwargs: Query parameters.
        :returns: requests.models.Response
        :throws: requests.exceptions.HTTPError
        """
        url = self.build_url(*args)
        json = kwargs.pop('json', None)
        LOGGER.info("PUT %s %r", url, kwargs)
        return self.raise_on_err(requests.put(url, params=kwargs,
                                              json=json, auth=self.userpass))

    def post(self, *args, **kwargs):
        """Send a POST request to ARI.

        :param args: Path segements.
        :param kwargs: Query parameters.
        :returns: requests.models.Response
        :throws: requests.exceptions.HTTPError
        """
        url = self.build_url(*args)
        json = kwargs.pop('json', None)
        LOGGER.info("POST %s %r", url, kwargs)
        return self.raise_on_err(requests.post(url, params=kwargs,
                                               json=json, auth=self.userpass))

    def delete(self, *args, **kwargs):
        """Send a DELETE request to ARI.

        :param args: Path segements.
        :param kwargs: Query parameters.
        :returns: requests.models.Response
        :throws: requests.exceptions.HTTPError
        """
        url = self.build_url(*args)
        LOGGER.info("DELETE %s %r", url, kwargs)
        return self.raise_on_err(requests.delete(url, params=kwargs,
                                                 auth=self.userpass))

    def request(self, method, *args, **kwargs):
        """ Send an arbitrary request to ARI.

        :param method: Method (get, post, delete, etc).
        :param args: Path segements.
        :param kwargs: Query parameters.
        :returns: requests.models.Response
        :throws: requests.exceptions.HTTPError
        """
        url = self.build_url(*args)
        LOGGER.info("%s %s %r", method, url, kwargs)
        requests_method = getattr(requests, method)
        return self.raise_on_err(requests_method(url, params=kwargs,
                                                 auth=self.userpass))

    def set_allow_errors(self, value):
        """Sets whether error responses returns exceptions.

        If True, then error responses are returned. Otherwise, methods throw
        an exception on error.

        :param value True/False value for allow_errors.
        """
        self.allow_errors = value

    def raise_on_err(self, resp):
        """Helper to raise an exception when a response is a 4xx or 5xx error.

        If allow_errors is True, then an exception is not raised.

        :param resp: requests.models.Response object
        :returns: resp
        """
        if not self.allow_errors and resp.status_code / 100 != 2:
            LOGGER.error('%s (%d %s): %r', resp.url, resp.status_code,
                         resp.reason, resp.text)
            resp.raise_for_status()
        return resp


class ARIRequest(object):
    """ Object that issues ARI requests and valiates response """

    def __init__(self, ari, config):
        self.ari = ari
        self.method = config['method']
        self.uri = config['uri']
        self.response_body = config.get('response_body')
        self.params = config.get('params') or {}
        self.body = config.get('body')
        self.instance = config.get('instance')
        self.delay = config.get('delay')
        self.expect = config.get('expect')
        self.headers = None

        if self.body:
            self.body = json.dumps(self.body)
            self.headers = {'Content-type': 'application/json'}

    def send(self, values):
        """Send this ARI request substituting the given values"""
        uri = var_replace(self.uri, values)
        url = self.ari.build_url(uri)
        requests_method = getattr(requests, self.method)
        params = dict((key, var_replace(val, values))
                      for key, val in self.params.iteritems())

        response = requests_method(
            url,
            params=params,
            data=self.body,
            headers=self.headers,
            auth=self.ari.userpass)

        if self.response_body:
            match = self.response_body.get('match')
            return all_match(match, response.json())

        if self.expect:
            if response.status_code != self.expect:
                LOGGER.error('sent %s %s %s expected %s response %d %s',
                             self.method, self.uri, self.params, self.expect,
                             response.status_code, response.text)
                return False
        else:
            if response.status_code / 100 != 2:
                LOGGER.error('sent %s %s %s response %d %s',
                             self.method, self.uri, self.params,
                             response.status_code, response.text)
                return False

        LOGGER.info('sent %s %s %s response %d %s',
                    self.method, self.uri, self.params,
                    response.status_code, response.text)
        return response


class EventMatcher(object):
    """Object to observe incoming events and match them against a config"""

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

        request_list = self.instance_config.get('requests') or []
        if isinstance(request_list, dict):
            request_list = [request_list]
        self.requests = [ARIRequest(ari, request_config)
                         for request_config in request_list]

        test_object.register_stop_observer(self.on_stop)

    def on_event(self, message):
        """Callback for every received ARI event.

        :param message: Parsed event from ARI WebSocket.
        """
        if self.matches(message):
            self.count += 1

            # send any associated requests
            for request in self.requests:
                if request.instance and request.instance != self.count:
                    continue
                if request.delay:
                    reactor.callLater(request.delay, request.send, message)
                else:
                    response = request.send(message)
                    if response is False:
                        self.passed = False

            # Split call and accumulation to always call the callback
            try:
                res = self.callback(self.ari, message, self.test_object)
                if res:
                    return True
                else:
                    LOGGER.error("Callback failed: %r",
                                 self.instance_config)
                    self.passed = False
            except:
                LOGGER.error("Exception in callback: %s",
                             traceback.format_exc())
                self.passed = False

        return False

    def on_stop(self, *args):
        """Callback for the end of the test.

        :param args: Ignored arguments.
        """
        if not self.count_range.contains(self.count):
            # max could be int or float('inf'); format with %r
            LOGGER.error("Expected %d <= count <= %r; was %d (%r)",
                         self.count_range.min_value, self.count_range.max_value,
                         self.count, self.conditions)
            self.passed = False
        self.test_object.set_passed(self.passed)

    def matches(self, message):
        """Compares a message against the configured conditions.

        :param message: Incoming ARI WebSocket event.
        :returns: True if message matches conditions; False otherwise.
        """
        match = self.conditions.get('match')
        res = all_match(match, message)

        # Now validate the nomatch, if it's there
        nomatch = self.conditions.get('nomatch')
        if res and nomatch:
            res = not all_match(nomatch, message)
        return res


class Range(object):
    """Utility object to handle numeric ranges (inclusive)."""

    def __init__(self, min_value=0, max_value=float("inf")):
        """Constructor.

        :param min: Minimum value of the range.
        :param max: Maximum value of the range.
        """
        self.min_value = min_value
        self.max_value = max_value

    def contains(self, value):
        """Checks if the given value is within this Range.

        :param value: Value to check.
        :returns: True/False if v is/isn't in the Range.
        """
        return self.min_value <= value <= self.max_value


def decode_range(yaml):
    """Parse a range from YAML specification."""

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


class ARIPluggableEventModule(object):
    """Subclass of ARIEventInstance that works with the pluggable event action
    module.
    """

    def __init__(self, test_object, triggered_callback, config):
        """Setup the ARI event observer"""
        self.test_object = test_object
        self.triggered_callback = triggered_callback
        if isinstance(config, list):
            self.config = config
        else:
            self.config = [config]
        for event_description in self.config:
            event_description["expected_count_range"] =\
                decode_range(event_description.get('count', 1))
            event_description["event_count"] = 0
        test_object.register_ws_event_handler(self.event_callback)
        test_object.register_stop_observer(self.on_stop)

    def event_callback(self, event):
        """Callback called when an event is received from ARI"""
        for event_description in self.config:
            match = event_description["match"]
            nomatch = event_description.get("nomatch", None)
            if not all_match(match, event):
                continue

            # Now validate the nomatch, if it's there
            if nomatch and all_match(nomatch, event):
                continue
            event_description["event_count"] += 1
            self.triggered_callback(self, self.test_object.ari, event)

    def on_stop(self, *args):
        """Callback for the end of the test.

        :param args: Ignored arguments.
        """
        for event_desc in self.config:
            if not event_desc["expected_count_range"].contains(event_desc["event_count"]):
                # max could be int or float('inf'); format with %r
                LOGGER.error("Expected %d <= count <= %r; was %d (%r, !%r)",
                             event_desc["expected_count_range"].min_value,
                             event_desc["expected_count_range"].max_value,
                             event_desc["event_count"],
                             event_desc["match"],
                             event_desc.get("nomatch", None))
                self.test_object.set_passed(False)
            self.test_object.set_passed(True)
PLUGGABLE_EVENT_REGISTRY.register("ari-events", ARIPluggableEventModule)


class ARIPluggableStartModule(object):
    """Pluggable ARI module that kicks off when Asterisk starts
    """

    def __init__(self, test_object, triggered_callback, config):
        """Constructor"""

        self.triggered_callback = triggered_callback
        self.test_object = test_object

        # AMI connects after ARI, so this should call back once we're
        # good and ready
        test_object.register_ami_observer(self.on_ami_connect)

    def on_ami_connect(self, ami):
        """AMI connect handler"""
        self.triggered_callback(self, self.test_object.ari, None)
PLUGGABLE_EVENT_REGISTRY.register("ari-start", ARIPluggableStartModule)


class ARIPluggableRequestModule(object):
    """Pluggable ARI action module.
    """

    def __init__(self, test_object, config):
        """Setup the ARI event observer"""
        self.test_object = test_object
        if not isinstance(config, list):
            config = [config]
        self.requests = [ARIRequest(test_object.ari, request_config)
                         for request_config in config]
        self.count = 0

    def run(self, triggered_by, source, extra):
        """Callback called when this action is triggered."""
        self.count += 1
        for request in self.requests:
            if request.instance and request.instance != self.count:
                continue
            if request.delay:
                reactor.callLater(request.delay, request.send, extra)
            else:
                result = request.send(extra)
                if isinstance(result, bool) and not result:
                    self.test_object.set_passed(False)
                else:
                    self.test_object.set_passed(True)
PLUGGABLE_ACTION_REGISTRY.register("ari-requests", ARIPluggableRequestModule)

# vim:sw=4:ts=4:expandtab:textwidth=79
