#!/usr/bin/env python
"""
Copyright (C) 2010-2014, Digium, Inc.
Paul Belanger <pabelanger@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging
import logging.config
import os
import traceback
import uuid
from datetime import datetime
from hashlib import md5
from twisted.internet import reactor, defer, error as twisted_error
from twisted.python import log
from starpy import manager, fastagi

from asterisk import Asterisk
from test_config import TestConfig
from test_conditions import TestConditionController
from version import AsteriskVersion


try:
    from pcap_listener import PcapListener
    PCAP_AVAILABLE = True
except:
    PCAP_AVAILABLE = False

LOGGER = None


def setup_logging(log_dir, log_full, log_messages):
    """Initialize the logger"""

    global LOGGER

    config_file = os.path.join(os.getcwd(), "logger.conf")
    if os.path.exists(config_file):
        try:
            logging.config.fileConfig(config_file, None, False)
        except:
            msg = ("WARNING: failed to preserve existing loggers - some "
                   "logging statements may be missing")
            print msg
            logging.config.fileConfig(config_file)
    else:
        msg = ("WARNING: no logging.conf file found; using default "
               "configuration")
        print msg
        logging.basicConfig(level=logging.DEBUG)

    root_logger = logging.getLogger()
    root_logger.setLevel(level=logging.DEBUG)

    LOGGER = logging.getLogger(__name__)

    fmt = '[%(asctime)s] %(levelname)s[%(process)d]: %(name)s:%(lineno)d '\
        '%(funcName)s: %(message)s'
    datefmt = '%b %d %H:%M:%S'
    form = logging.Formatter(fmt=fmt, datefmt=datefmt)

    if log_full:
        full_handler = logging.FileHandler(os.path.join(log_dir, 'full.txt'))
        full_handler.setLevel(logging.DEBUG)
        full_handler.setFormatter(form)
        root_logger.addHandler(full_handler)

    if log_messages:
        messages_handler = logging.FileHandler(os.path.join(log_dir, 'messages.txt'))
        messages_handler.setLevel(logging.INFO)
        messages_handler.setFormatter(form)
        root_logger.addHandler(messages_handler)


class TestCase(object):
    """The base class object for python tests. This class provides common
    functionality to all tests, including management of Asterisk instances, AMI,
    twisted reactor, and various other utilities.
    """

    def __init__(self, test_path='', test_config=None):
        """Create a new instance of a TestCase. Must be called by inheriting
        classes.

        Keyword Arguments:
        test_path Optional parameter that specifies the path where this test
                  resides
        test_config Loaded YAML test configuration
        """

        if not len(test_path):
            self.test_name = os.path.dirname(sys.argv[0])
        else:
            self.test_name = test_path

        # We're not using /tmp//full//test//name because it gets so long that
        # it doesn't fit in AF_UNIX paths (limited to around 108 chars) used
        # for the rasterisk CLI connection. As a quick fix, we hash the path
        # using md5, to make it unique enough.
        self.realbase = self.test_name.replace("tests/", "", 1)
        self.base = md5(self.realbase).hexdigest()
        # We provide a symlink to it from a named path.
        named_dir = os.path.join(Asterisk.test_suite_root, self.realbase)
        try:
            os.makedirs(os.path.dirname(named_dir))
        except OSError:
            pass
        try:
            join_path = os.path.relpath(
                os.path.join(Asterisk.test_suite_root, self.base),
                os.path.dirname(named_dir)
            )
            os.symlink(join_path, named_dir)
        except OSError:
            pass

        self.ast = []
        self.ami = []
        self.fastagi = []
        self.base_config_path = None
        self.reactor_timeout = 30
        self.passed = None
        self.fail_tokens = []
        self.timeout_id = None
        self.global_config = TestConfig(os.getcwd())
        self.test_config = TestConfig(self.test_name, self.global_config)
        self.condition_controller = None
        self.pcap = None
        self.pcapfilename = None
        self.create_pcap = False
        self._stopping = False
        self.testlogdir = self._set_test_log_directory()
        self.ast_version = AsteriskVersion()
        self._start_callbacks = []
        self._stop_callbacks = []
        self._ami_connect_callbacks = []
        self._ami_reconnect_callbacks = []
        self._pcap_callbacks = []
        self._stop_deferred = None
        log_full = True
        log_messages = True

        if os.getenv("VALGRIND_ENABLE") == "true":
            self.reactor_timeout *= 20

        # Pull additional configuration from YAML config if possible
        if test_config:
            if 'config-path' in test_config:
                self.base_config_path = test_config['config-path']
            if 'reactor-timeout' in test_config:
                self.reactor_timeout = test_config['reactor-timeout']
            if 'memcheck-delay-stop' in test_config:
                # minimum reactor timeout 3 seconds more than memcheck-delay-stop.
                delay = test_config['memcheck-delay-stop'] + 3
                if delay > self.reactor_timeout:
                    self.reactor_timeout = delay
            self.ast_conf_options = test_config.get('ast-config-options')
            log_full = test_config.get('log-full', True)
            log_messages = test_config.get('log-messages', True)
            self.allow_ami_reconnects = test_config.get('allow-ami-reconnects', False)
        else:
            self.ast_conf_options = None
            self.allow_ami_reconnects = False

        os.makedirs(self.testlogdir)

        # Set up logging
        setup_logging(self.testlogdir, log_full, log_messages)

        LOGGER.info("Executing " + self.test_name)

        if PCAP_AVAILABLE and os.getenv("PCAP", "no") == "yes":
            # This PcapListener is from pcap_listener NOT from asterisk/pcap.
            # The former is standalone, which we need here, while the latter
            # is meant for use by tests.
            # It's triggered by the --pcap command line.
            dumpfile = os.path.join(self.testlogdir, "packet.pcap")
            PcapListener("lo", dumpfile=dumpfile)

        self._setup_conditions()

        # Enable twisted logging
        observer = log.PythonLoggingObserver()
        observer.start()

        reactor.callWhenRunning(self._run)

    def _set_test_log_directory(self):
        """Determine which logging directory we should use for this test run

        Returns:
        The full path that should be used as the directory for all log data
        """
        i = 1
        base_path = os.path.join(Asterisk.test_suite_root, self.base)
        while os.path.isdir(os.path.join(base_path, "run_%d" % i)):
            i += 1
        full_path = os.path.join(base_path, "run_%d" % i)
        return full_path

    def _setup_conditions(self):
        """Register pre and post-test conditions.

        Note that we have to first register condition checks without related
        conditions, so that those that have dependencies can find them
        """
        self.condition_controller = TestConditionController(self.test_config,
                                                            self.ast,
                                                            self.stop_reactor)
        global_conditions = self.global_config.get_conditions()
        conditions = self.test_config.get_conditions()

        # Get those global conditions that are not in the self conditions
        for g_cond in global_conditions:
            disallowed = [i for i in conditions
                          if i[0].get_name() == g_cond[0].get_name() and
                          i[1] == g_cond[1]]
            if len(disallowed) == 0:
                conditions.append(g_cond)

        for cond in conditions:
            # cond is a 3-tuple of object, pre-post type, and related name
            obj, pre_post_type, related_name = cond
            if pre_post_type == "PRE":
                self.condition_controller.register_pre_test_condition(obj)
            elif pre_post_type == "POST":
                self.condition_controller.register_post_test_condition(obj, related_name)
            else:
                msg = "Unknown condition type [%s]" % pre_post_type
                LOGGER.warning(msg)
        self.condition_controller.register_observer(
            self.handle_condition_failure, 'Failed')

    def get_asterisk_hosts(self, count):
        """Return a list of host dictionaries for Asterisk instances

        Keyword Arguments:
        count  The number of Asterisk instances to create, if no remote
               Asterisk instances have been specified
        """
        if (self.global_config.config and
                'asterisk-instances' in self.global_config.config):
            asterisks = self.global_config.config.get('asterisk-instances')
        else:
            asterisks = [{'num': i + 1, 'host': '127.0.0.%d' % (i + 1)}
                         for i in range(count)]
        return asterisks

    def create_asterisk(self, count=1, base_configs_path=None, test_config=None):
        """Create n instances of Asterisk

        Note: if the instances of Asterisk being created are remote, the
        keyword arguments to this function are ignored.

        Keyword arguments:
        count             The number of Asterisk instances to create.  Each
                          Asterisk instance will be hosted on 127.0.0.x, where x
                          is the 1-based index of the instance created.
        base_configs_path Provides common configuration for Asterisk instances
                          to use. This is useful for certain test types that use
                          the same configuration all the time. This
                          configuration can be overwritten by individual tests,
                          however.
        test_config       Test Configuration
        """
        for i, ast_config in enumerate(self.get_asterisk_hosts(count)):
            local_num = ast_config.get('num')
            host = ast_config.get('host')

            if not host:
                msg = "Cannot manage Asterisk instance without 'host'"
                raise Exception(msg)

            if local_num:
                LOGGER.info("Creating Asterisk instance %d" % local_num)
                ast_instance = Asterisk(base=self.testlogdir, host=host,
                                        ast_conf_options=self.ast_conf_options,
                                        test_config=test_config)
            else:
                LOGGER.info("Managing Asterisk instance at %s" % host)
                ast_instance = Asterisk(base=self.testlogdir, host=host,
                                        remote_config=ast_config,
                                        test_config=test_config)
            self.ast.append(ast_instance)
            self.condition_controller.register_asterisk_instance(self.ast[i])

            if local_num:
                # If a base configuration for this Asterisk instance has been
                # provided, install it first
                if base_configs_path is None:
                    base_configs_path = self.base_config_path
                if base_configs_path:
                    ast_dir = "%s/ast%d" % (base_configs_path, local_num)
                    self.ast[i].install_configs(ast_dir,
                                                self.test_config.get_deps())
                # Copy test specific config files
                self.ast[i].install_configs("%s/configs/ast%d" %
                                            (self.test_name, local_num),
                                            self.test_config)

    def create_ami_factory(self, count=1, username="user", secret="mysecret",
                           port=5038):
        """Create n instances of AMI.  Each AMI instance will attempt to connect
        to a previously created instance of Asterisk.  When a connection is
        complete, the ami_connect method will be called.

        Keyword arguments:
        count    The number of instances of AMI to create
        username The username to login with
        secret   The password to login with
        port     The port to connect over
        """

        def on_reconnect(login_deferred):
            """Called if the connection is lost and re-made"""
            login_deferred.addCallbacks(self._ami_reconnect, self.ami_login_error)

        for i, ast_config in enumerate(self.get_asterisk_hosts(count)):
            host = ast_config.get('host')
            ami_config = ast_config.get('ami', {})
            actual_user = ami_config.get('username', username)
            actual_secret = ami_config.get('secret', secret)
            actual_port = ami_config.get('port', port)

            self.ami.append(None)
            LOGGER.info("Creating AMIFactory %d to %s" % ((i + 1), host))
            if self.allow_ami_reconnects:
                try:
                    ami_factory = manager.AMIFactory(actual_user, actual_secret, i,
                                                     on_reconnect=on_reconnect)
                except:
                    LOGGER.error("starpy.manager.AMIFactory doesn't support reconnects")
                    LOGGER.error("starpy needs to be updated to run this test")
                    self.passed = False
                    self.stop_reactor()
                    return
            else:
                ami_factory = manager.AMIFactory(actual_user, actual_secret, i)
            deferred = ami_factory.login(ip=host, port=actual_port)
            deferred.addCallbacks(self._ami_connect, self.ami_login_error)

    def create_fastagi_factory(self, count=1):
        """Create n instances of AGI.  Each AGI instance will attempt to connect
        to a previously created instance of Asterisk.  When a connection is
        complete, the fastagi_connect method will be called.

        Keyword arguments:
        count The number of instances of AGI to create
        """

        for i, ast_config in enumerate(self.get_asterisk_hosts(count)):
            host = ast_config.get('host')

            self.fastagi.append(None)
            LOGGER.info("Creating FastAGI Factory %d" % (i + 1))
            fastagi_factory = fastagi.FastAGIFactory(self.fastagi_connect)
            reactor.listenTCP(4573, fastagi_factory,
                              self.reactor_timeout, host)

    def fastagi_connect(self, agi):
        """Callback called by starpy when FastAGI connects

        This method should be overridden by derived classes that use
        create_fastagi_factory

        Keyword arguments:
        agi The AGI manager
        """
        pass

    def create_pcap_listener(self, device=None, bpf_filter=None, dumpfile=None,
                             snaplen=None, buffer_size=None):
        """Create a single instance of a pcap listener.

        Keyword arguments:
        device      The interface to listen on. Defaults to the first interface
                    beginning with 'lo'.
        bpf_filter  BPF (filter) describing what packets to match, i.e.
                    "port 5060"
        dumpfile    The filename at which to save a pcap capture
        snaplen     Number of bytes to capture from each packet. Defaults to
                    65535.
        buffer_size The ring buffer size. Defaults to 0.

        """

        if not PCAP_AVAILABLE:
            msg = ("PCAP not available on this machine. "
                   "Test config is missing pcap dependency.")
            raise Exception(msg)

        # TestCase will create a listener for logging purposes, and individual
        # tests can create their own. Tests may only want to watch a specific
        # port, while a general logger will want to watch more general traffic
        # which can be filtered later.
        return PcapListener(device, bpf_filter, dumpfile, self._pcap_callback,
                            snaplen, buffer_size)

    def start_asterisk(self):
        """This method will be called when the reactor is running, but
        immediately before instances of Asterisk are launched. Derived classes
        can override this if needed.
        """
        pass

    def _start_asterisk(self):
        """Start the instances of Asterisk that were previously created. See
        create_asterisk. Note that this should be the first thing called
        when the reactor has started to run
        """
        def __check_success_failure(result):
            """Make sure the instances started properly"""
            for (success, value) in result:
                if not success:
                    LOGGER.error(value.getErrorMessage())
                    self.stop_reactor()
            return result

        def __perform_pre_checks(result):
            """Execute the pre-condition checks"""
            deferred = self.condition_controller.evaluate_pre_checks()
            if deferred is None:
                return result
            else:
                return deferred

        def __run_callback(result):
            """Notify the test that we are running"""
            for callback in self._start_callbacks:
                callback(self.ast)
            self.run()
            return result

        # Call the method that derived objects can override
        self.start_asterisk()

        # Gather up the deferred objects from each of the instances of Asterisk
        # and wait until all are finished before proceeding
        start_defers = []
        for index, ast in enumerate(self.ast):
            LOGGER.info("Starting Asterisk instance %d" % (index + 1))
            temp_defer = ast.start(self.test_config.get_deps())
            start_defers.append(temp_defer)

        deferred = defer.DeferredList(start_defers, consumeErrors=True)
        deferred.addCallback(__check_success_failure)
        deferred.addCallback(__perform_pre_checks)
        deferred.addCallback(__run_callback)

    def stop_asterisk(self):
        """This method is called when the reactor is running but immediately
        before instances of Asterisk are stopped. Derived classes can override
        this method if needed.
        """
        pass

    def _stop_asterisk(self):
        """Stops the instances of Asterisk.

        Returns:
        A deferred object that can be used to be notified when all instances
        of Asterisk have stopped.
         """
        def __check_success_failure(result):
            """Make sure the instances stopped properly"""
            for (success, value) in result:
                if not success:
                    LOGGER.warning(value.getErrorMessage())
                    # This should already be called when the reactor is being
                    # terminated. If we couldn't stop the instance of Asterisk,
                    # there isn't much else to do here other then complain
            self._stop_deferred.callback(self)
            return result

        def __stop_instances(result):
            """Stop the instances"""

            # Call the overridable method now
            self.stop_asterisk()
            # Gather up the stopped defers; check success failure of stopping
            # when all instances of Asterisk have stopped
            stop_defers = []
            for index, ast in enumerate(self.ast):
                LOGGER.info("Stopping Asterisk instance %d" % (index + 1))
                temp_defer = ast.stop()
                stop_defers.append(temp_defer)

            defer.DeferredList(stop_defers).addCallback(
                __check_success_failure)
            return result

        self._stop_deferred = defer.Deferred()
        deferred = self.condition_controller.evaluate_post_checks()
        if deferred:
            deferred.addCallback(__stop_instances)
        else:
            __stop_instances(None)
        return self._stop_deferred

    def stop_reactor(self):
        """Stop the reactor and cancel the test."""

        def __stop_reactor(result):
            """Called when the Asterisk instances are stopped"""
            LOGGER.info("Stopping Reactor")
            if reactor.running:
                try:
                    reactor.stop()
                except twisted_error.ReactorNotRunning:
                    # Something stopped it between our checks - at least we're
                    # stopped
                    pass
            return result
        if not self._stopping:
            self._stopping = True
            deferred = self._stop_asterisk()
            for callback in self._stop_callbacks:
                deferred.addCallback(callback)
            deferred.addCallback(__stop_reactor)

    def _reactor_timeout(self):
        """A wrapper function for stop_reactor(), so we know when a reactor
        timeout has occurred.
        """
        if not self._stopping:
            LOGGER.warning("Reactor timeout: '%s' seconds" % self.reactor_timeout)
            self.on_reactor_timeout()
            self.stop_reactor()
        else:
            LOGGER.info("Reactor timeout: '%s' seconds (ignored; already stopping)"
                        % self.reactor_timeout)

    def on_reactor_timeout(self):
        """Virtual method called when reactor times out"""
        pass

    def _run(self):
        """Private entry point called when the reactor first starts up. This
        needs to first ensure that Asterisk is fully up and running before
        moving on.
        """
        if self.ast:
            self._start_asterisk()
        else:
            # If no instances of Asterisk are needed, go ahead and just run
            self.run()

    def run(self):
        """Base implementation of the test execution method, run. Derived
        classes should override this and start their Asterisk dependent logic
        from this method.

        Derived classes must call this implementation, as this method provides a
        fail out mechanism in case the test hangs.
        """
        if self.reactor_timeout > 0:
            self.timeout_id = reactor.callLater(self.reactor_timeout,
                                                self._reactor_timeout)

    def ami_login_error(self, reason):
        """Handler for login errors into AMI. This will stop the test.

        Keyword arguments:
        ami The instance of AMI that raised the login error
        """
        LOGGER.error("Error logging into AMI: %s" % reason.getErrorMessage())
        LOGGER.error(reason.getTraceback())
        self.stop_reactor()
        return reason

    def ami_connect(self, ami):
        """Virtual method used after create_ami_factory() successfully logs into
        the Asterisk AMI.
        """
        pass

    def _ami_connect(self, ami):
        """Callback when AMI first connects"""
        LOGGER.info("AMI Connect instance %s" % (ami.id + 1))
        self.ami[ami.id] = ami
        try:
            for callback in self._ami_connect_callbacks:
                callback(ami)
            self.ami_connect(ami)
        except:
            LOGGER.error("Exception raised in ami_connect:")
            LOGGER.error(traceback.format_exc())
            self.stop_reactor()
        return ami

    def ami_reconnect(self, ami):
        """Virtual method used after create_ami_factory() successfully re-logs into
        the Asterisk AMI.
        """
        pass

    def _ami_reconnect_fully_booted(self, ami, event):
        """Callback when AMI reconnects and is fully booted"""
        LOGGER.info("AMI Reconnect instance %s is fully booted" % (ami.id + 1))
        ami.deregisterEvent('FullyBooted', self._ami_reconnect_fully_booted)
        try:
            for callback in self._ami_reconnect_callbacks:
                callback(ami)
            self.ami_reconnect(ami)
        except:
            LOGGER.error("Exception raised in ami_reconnect:")
            LOGGER.error(traceback.format_exc())
            self.stop_reactor()
        return (ami, event)

    def _ami_reconnect(self, ami):
        """Callback when AMI initially reconnects"""
        LOGGER.info("AMI Reconnect instance %s" % (ami.id + 1))
        self.ami[ami.id] = ami
        ami.registerEvent('FullyBooted', self._ami_reconnect_fully_booted)
        return ami

    def pcap_callback(self, packet):
        """Virtual method used to receive captured packets."""
        pass

    def _pcap_callback(self, packet):
        """Packet capture callback"""
        self.pcap_callback(packet)
        for callback in self._pcap_callbacks:
            callback(packet)

    def handle_originate_failure(self, reason):
        """Fail the test on an Originate failure

        Convenience callback handler for twisted deferred errors for an AMI
        originate call. Derived classes can choose to add this handler to
        originate calls in order to handle them safely when they fail.
        This will stop the test if called.

        Keyword arguments:
        reason The reason the originate failed
        """
        LOGGER.error("Error sending originate: %s" % reason.getErrorMessage())
        LOGGER.error(reason.getTraceback())
        self.stop_reactor()
        return reason

    def reset_timeout(self):
        """Resets the reactor timeout"""
        if self.timeout_id is not None:
            original_time = datetime.fromtimestamp(self.timeout_id.getTime())
            self.timeout_id.reset(self.reactor_timeout)
            new_time = datetime.fromtimestamp(self.timeout_id.getTime())
            msg = ("Reactor timeout originally scheduled for %s, "
                   "rescheduled for %s" % (str(original_time), str(new_time)))
            LOGGER.info(msg)

    def handle_condition_failure(self, test_condition):
        """Callback handler for condition failures"""
        if test_condition.pass_expected:
            msg = ("Test Condition %s failed; setting passed status to False" %
                   test_condition.get_name())
            LOGGER.error(msg)
            self.passed = False
        else:
            msg = ("Test Condition %s failed but expected failure was set; "
                   "test status not modified" % test_condition.get_name())
            LOGGER.info(msg)

    def evaluate_results(self):
        """Return whether or not the test has passed"""

        while len(self.fail_tokens):
            fail_token = self.fail_tokens.pop(0)
            LOGGER.error("Fail token present: %s" % fail_token['message'])
            self.passed = False

        return self.passed

    def register_pcap_observer(self, callback):
        """Register an observer that will be called when a packet is received
        from a created pcap listener

        Keyword Arguments:
        callback The callback to receive the packet. The callback function
                 should take in a single parameter, which will be the packet
                 received
        """
        self._pcap_callbacks.append(callback)

    def register_start_observer(self, callback):
        """Register an observer that will be called when all Asterisk instances
        have started

        Keyword Arguments:
        callback The deferred callback function to be called when all instances
                 of Asterisk have started. The callback should take no
                 parameters.
        """
        self._start_callbacks.append(callback)

    def register_stop_observer(self, callback):
        """Register an observer that will be called when Asterisk is stopped

        Keyword Arguments:
        callback The deferred callback function to be called when Asterisk is
                 stopped

        Note:
        This appends a callback to the deferred chain of callbacks executed when
        all instances of Asterisk are stopped.
        """
        self._stop_callbacks.append(callback)

    def register_ami_observer(self, callback):
        """Register an observer that will be called when TestCase connects with
        Asterisk over the Manager interface

        Parameters:
        callback The deferred callback function to be called when AMI connects
        """
        self._ami_connect_callbacks.append(callback)

    def register_ami_reconnect_observer(self, callback):
        """Register an observer that will be called when TestCase reconnects with
        Asterisk over the Manager interface

        Parameters:
        callback The deferred callback function to be called when AMI reconnects
        """
        self._ami_reconnect_callbacks.append(callback)

    def create_fail_token(self, message):
        """Add a fail token to the test. If any fail tokens exist at the end of
        the test, the test will fail.

        Keyword Arguments:
        message A text message describing the failure

        Returns:
        A token that can be removed from the test at a later time, if the test
        should pass
        """
        fail_token = {'uuid': uuid.uuid4(), 'message': message}
        self.fail_tokens.append(fail_token)
        return fail_token

    def remove_fail_token(self, fail_token):
        """Remove a fail token from the test.

        Keyword Arguments:
        fail_token A previously created fail token to be removed from the test
        """
        if fail_token not in self.fail_tokens:
            LOGGER.warning('Attempted to remove an unknown fail token: %s',
                           fail_token['message'])
            self.passed = False
            return
        self.fail_tokens.remove(fail_token)

    def set_passed(self, value):
        """Accumulate pass/fail value.

        If a test module has already claimed that the test has failed, then this
        method will ignore any further attempts to change the pass/fail status.
        """
        if self.passed is False:
            return
        self.passed = value


class SimpleTestCase(TestCase):
    """The base class for extremely simple tests requiring only a spawned call
    into the dialplan where success can be reported via a user-defined AMI
    event.
    """

    default_expected_events = 1

    default_channel = 'Local/100@test'

    default_application = 'Echo'

    def __init__(self, test_path='', test_config=None):
        """Constructor

        Parameters:
        test_path Optional path to the location of the test directory
        test_config Optional yaml loaded object containing config information
        """
        TestCase.__init__(self, test_path, test_config=test_config)

        self._test_runs = []
        self._current_run = 0
        self._event_count = 0
        self.expected_events = SimpleTestCase.default_expected_events
        self._tracking_channels = []
        self._ignore_originate_failures = False
        self._spawn_after_hangup = False
        self._end_test_delay = 0
        self._stop_on_end = True

        if test_config is None or 'test-iterations' not in test_config:
            # No special test configuration defined, use defaults
            variables = {'testuniqueid': '%s' % (str(uuid.uuid1())), }
            defaults = {'channel': SimpleTestCase.default_channel,
                        'application': SimpleTestCase.default_application,
                        'variable': variables, }
            self._test_runs.append(defaults)
        else:
            # Use the info in the test config to figure out what we want to run
            for iteration in test_config['test-iterations']:
                variables = {'testuniqueid': '%s' % (str(uuid.uuid1())), }
                iteration['variable'] = variables
                self._test_runs.append(iteration)
            if 'expected_events' in test_config:
                self.expected_events = test_config['expected_events']
            if 'ignore-originate-failures' in test_config:
                self._ignore_originate_failures =\
                    test_config['ignore-originate-failures']
            if 'spawn-after-hangup' in test_config:
                self._spawn_after_hangup = test_config['spawn-after-hangup']
            self._end_test_delay = test_config.get('end-test-delay') or 0
            self._stop_on_end = test_config.get('stop-on-end', True)

        self.create_asterisk(count=1, test_config=test_config)

    def ami_connect(self, ami):
        """AMI connect handler"""

        if self.expected_events != 0:
            ami.registerEvent('UserEvent', self.__event_cb)
        ami.registerEvent('Hangup', self.__hangup_cb)
        ami.registerEvent('VarSet', self.__varset_cb)

        # Kick off the test runs
        self.__start_new_call(ami)

    def __originate_call(self, ami, call_details):
        """Actually originate a call

        Parameters:
        ami The AMI connection object
        call_details A dictionary object containing the parameters to pass
            to the originate
        """

        def __swallow_originate_error(result):
            """Nom nom nom"""
            return

        # Each originate call gets tagged with the channel variable
        # 'testuniqueid', which contains a UUID as the value.  When a VarSet
        # event happens, it will contain the Asterisk channel name with the
        # unique ID we've assigned, allowing us to associate the Asterisk
        # channel name with the channel we originated
        msg = "Originating call to %s" % call_details['channel']
        if 'account' not in call_details:
            call_details['account'] = None
        if 'async' not in call_details:
            call_details['async'] = False
        if 'channelid' not in call_details:
            call_details['channelid'] = None
        if 'otherchannelid' not in call_details:
            call_details['otherchannelid'] = None
        if 'application' in call_details:
            msg += " with application %s" % call_details['application']
            deferred = ami.originate(
                channel=call_details['channel'],
                application=call_details['application'],
                variable=call_details['variable'],
                account=call_details['account'],
                async=call_details['async'],
                channelid=call_details['channelid'],
                otherchannelid=call_details['otherchannelid'])
        else:
            msg += " to %s@%s at %s" % (call_details['exten'],
                                        call_details['context'],
                                        call_details['priority'],)
            deferred = ami.originate(
                channel=call_details['channel'],
                context=call_details['context'],
                exten=call_details['exten'],
                priority=call_details['priority'],
                variable=call_details['variable'],
                account=call_details['account'],
                async=call_details['async'],
                channelid=call_details['channelid'],
                otherchannelid=call_details['otherchannelid'])
        if self._ignore_originate_failures:
            deferred.addErrback(__swallow_originate_error)
        else:
            deferred.addErrback(self.handle_originate_failure)
        LOGGER.info(msg)

    def __varset_cb(self, ami, event):
        """VarSet event handler.  This event helps us tie back the channel
        name that Asterisk created with the call we just originated
        """

        if event['variable'] == 'testuniqueid':

            if (len([chan for chan in self._tracking_channels if
                     chan['testuniqueid'] == event['value']])):
                # Duplicate event, return
                return

            # There should only ever be one match, since we're
            # selecting on a UUID
            originating_channel = [chan for chan in self._test_runs
                                   if (chan['variable']['testuniqueid'] ==
                                       event['value'])][0]
            self._tracking_channels.append({
                'channel': event['channel'],
                'testuniqueid': event['value'],
                'originating_channel': originating_channel})
            LOGGER.debug("Tracking originated channel %s as %s (ID %s)" % (
                originating_channel, event['channel'], event['value']))

    def __hangup_cb(self, ami, event):
        """Hangup Event handler.

        If configured to do so, this will spawn the next new call
        """

        candidate_channel = [chan for chan in self._tracking_channels
                             if chan['channel'] in event['channel']]
        if len(candidate_channel):
            LOGGER.debug("Channel %s hung up; removing" % event['channel'])
            self._tracking_channels.remove(candidate_channel[0])
            if self._spawn_after_hangup:
                self._current_run += 1
                self.__start_new_call(ami)

    def __start_new_call(self, ami):
        """Kick off the next new call, or, if we've run out of calls to make,
        stop the test if configured to do so
        """

        if self._current_run < len(self._test_runs):
            self.__originate_call(ami, self._test_runs[self._current_run])
        else:
            LOGGER.info("All calls executed")
            if self._stop_on_end:
                LOGGER.info("Stopping")
                reactor.callLater(self._end_test_delay, self.stop_reactor)

    def __event_cb(self, ami, event):
        """UserEvent callback handler.

        This is the default way in which new calls are kicked off.
        """

        if self.verify_event(event):
            self._event_count += 1
            if self._event_count == self.expected_events:
                self.passed = True
                LOGGER.info("Test ending, hanging up current channels")
                for chan in self._tracking_channels:
                    deferred = self.ami[0].hangup(chan['channel'])
                    deferred.addCallbacks(self.hangup, self.hangup_error)
            else:
                self._current_run += 1
                self.__start_new_call(ami)

    def hangup(self, result):
        """Called when all channels are hung up"""

        LOGGER.info("Hangup complete, stopping reactor")
        self.stop_reactor()

    def hangup_error(self, result):
        """Called when an error occurs during a hangup"""
        # Ignore the hangup error - in this case, the channel was disposed of
        # prior to our hangup request, which is okay
        reactor.callLater(self._end_test_delay, self.stop_reactor)

    def verify_event(self, event):
        """Virtual method used to verify values in the event."""
        return True

    def run(self):
        """Run the test!"""
        TestCase.run(self)
        self.create_ami_factory()


class TestCaseModule(TestCase):
    """The most basic of test objects for a pluggable module.

    This wraps the TestCase class such that it can be used and configured from
    YAML.
    """

    def __init__(self, test_path='', test_config=None):
        """Constructor

        :param test_path Full path to the test location
        :param test_config The YAML provided test configuration for this object
        """
        if not test_config:
            test_config = {}

        super(TestCaseModule, self).__init__(test_path, test_config)

        self.asterisk_instances = test_config.get('asterisk-instances') or 1
        self.connect_ami = test_config.get('connect-ami') or False
        self.connect_agi = test_config.get('connect-agi') or False

        self.create_asterisk(count=self.asterisk_instances, test_config=test_config)

    def run(self):
        """The reactor entry point"""
        super(TestCaseModule, self).run()

        if self.connect_ami:
            if not isinstance(self.connect_ami, dict):
                self.create_ami_factory(count=self.asterisk_instances)
            else:
                self.create_ami_factory(**self.connect_ami)
        if self.connect_agi:
            if not isinstance(self.connect_agi, dict):
                self.create_fastagi_factory(count=self.asterisk_instances)
            else:
                self.create_fastagi_factory(**self.connect_agi)
