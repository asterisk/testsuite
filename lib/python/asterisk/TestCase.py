#!/usr/bin/env python
'''
Copyright (C) 2010, Digium, Inc.
Paul Belanger <pabelanger@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging
import logging.config
import os
import datetime
import time
from twisted.internet import reactor, defer
from twisted.python import failure
from starpy import manager, fastagi

from asterisk import Asterisk
from TestConfig import TestConfig
from TestConditions import TestConditionController, TestCondition
from ThreadTestCondition import ThreadPreTestCondition, ThreadPostTestCondition
from version import AsteriskVersion


try:
    from pcap_listener import PcapListener
    PCAP_AVAILABLE = True
except:
    PCAP_AVAILABLE = False

logger = logging.getLogger(__name__)

class TestCase(object):
    """
    The base class object for python tests.  This class provides common functionality to all
    tests, including management of Asterisk instances, AMI, Twisted Reactor, and various
    other utilities.
    """

    def __init__(self):
        """
        Create a new instance of a TestCase.  Must be called by inheriting
        classes.
        """

        self.test_name = os.path.dirname(sys.argv[0])
        self.base = self.test_name.replace("tests/", "", 1)
        self.ast = []
        self.ami = []
        self.fastagi = []
        self.reactor_timeout = 30
        self.passed = False
        self.defaultLogLevel = "WARN"
        self.defaultLogFileName = "logger.conf"
        self.timeoutId = None
        self.global_config = TestConfig(os.getcwd())
        self.test_config = TestConfig(self.test_name, self.global_config)
        self.testStateController = None
        self.pcap = None
        self.pcapfilename = None
        self.__stopping = False
        self.testlogdir = os.path.join(Asterisk.test_suite_root, self.base, str(os.getpid()))
        self.ast_version = AsteriskVersion()

        os.makedirs(self.testlogdir)

        """ Set up logging """
        logConfigFile = os.path.join(os.getcwd(), "%s" % (self.defaultLogFileName))
        if os.path.exists(logConfigFile):
            try:
                logging.config.fileConfig(logConfigFile, None, False)
            except:
                print "WARNING: failed to preserve existing loggers - some logging statements may be missing"
                logging.config.fileConfig(logConfigFile)
        else:
            print "WARNING: no logging.conf file found; using default configuration"
            logging.basicConfig(level=self.defaultLogLevel)

        if PCAP_AVAILABLE:
            self.pcapfilename = os.path.join(self.testlogdir, "dumpfile.pcap")
            self.pcap = self.create_pcap_listener(dumpfile=self.pcapfilename)

        self.testConditionController = TestConditionController(self.test_config, self.ast, self.stop_reactor)
        self.__setup_conditions()

        logger.info("Executing " + self.test_name)
        reactor.callWhenRunning(self.__run)

    def __setup_conditions(self):
        """
        Register pre and post-test conditions.  Note that we have to first register condition checks
        without related conditions, so that those that have dependencies can find them
        """
        self.global_conditions = self.global_config.get_conditions()
        self.conditions = self.test_config.get_conditions()

        """ If there are no global conditions return """
        if (len(self.global_conditions) == 0):
            return

        """ Get those global conditions that are not in the self conditions """
        for g in self.global_conditions:
            disallowed = [i for i in self.conditions if i[0].getName() == g[0].getName() and i[1] == g[1]]
            if (len(disallowed) == 0):
                self.conditions.append(g)

        for c in self.conditions:
            """ c is a 3-tuple of object, pre-post type, and related name """
            if (c[2] == ""):
                if (c[1] == "PRE"):
                    self.testConditionController.register_pre_test_condition(c[0])
                elif (c[1] == "POST"):
                    self.testConditionController.register_post_test_condition(c[0])
                else:
                    logger.warning("Unknown condition type [%s]" % c[1])
        for c in self.conditions:
            if (c[2] != ""):
                if (c[1] == "POST"):
                    self.testConditionController.register_post_test_condition(c[0], c[2])
                else:
                    logger.warning("Unsupported type [%s] with related condition %s" % (c[1], c[2]))
        self.testConditionController.register_observer(self.handle_condition_failure, 'Failed')

    def create_asterisk(self, count=1):
        """
        Create n instances of Asterisk

        Keyword arguments:
        count -- the number of Asterisk instances to create.  Each Asterisk instance
        will be hosted on 127.0.0.x, where x is the 1-based index of the instance
        created

        """
        for c in range(count):
            logger.info("Creating Asterisk instance %d" % (c + 1))
            host = "127.0.0.%d" % (c + 1)
            self.ast.append(Asterisk(base=self.base, host=host))
            """ Copy test specific config files """
            self.ast[c].install_configs("%s/configs/ast%d" %
                    (self.test_name, c + 1))

    def create_ami_factory(self, count=1, username="user", secret="mysecret", port=5038):
        """
        Create n instances of AMI.  Each AMI instance will attempt to connect to
        a previously created instance of Asterisk.  When a connection is complete,
        the ami_connect method will be called.

        Keyword arguments:
        count -- The number of instances of AMI to create
        username -- The username to login with
        secret -- The password to login with
        port -- The port to connect over

        """

        for c in range(count):
            host = "127.0.0.%d" % (c + 1)
            self.ami.append(None)
            logger.info("Creating AMIFactory %d" % (c + 1))
            self.ami_factory = manager.AMIFactory(username, secret, c)
            self.ami_factory.login(host).addCallbacks(self.__ami_connect,
                self.ami_login_error)

    def create_fastagi_factory(self, count=1):
        """
        Create n instances of AGI.  Each AGI instance will attempt to connect to
        a previously created instance of Asterisk.  When a connection is complete,
        the fastagi_connect method will be called.

        Keyword arguments:
        count -- The number of instances of AGI to create

        """

        for c in range(count):
            host = "127.0.0.%d" % (c + 1)
            self.fastagi.append(None)
            logger.info("Creating FastAGI Factory %d" % (c + 1))
            self.fastagi_factory = fastagi.FastAGIFactory(self.fastagi_connect)
            reactor.listenTCP(4573, self.fastagi_factory,
                    self.reactor_timeout, host)

    def create_pcap_listener(self, device=None, bpf_filter=None, dumpfile=None):
        """Create a single instance of a pcap listener.

        Keyword arguments:
        device -- The interface to listen on. Defaults to the first interface beginning with 'lo'.
        bpf_filter -- BPF (filter) describing what packets to match, i.e. "port 5060"
        dumpfile -- The filename at which to save a pcap capture

        """

        if not PCAP_AVAILABLE:
            raise Exception("PCAP not available on this machine. Test config is missing pcap dependency.")

        # TestCase will create a listener for logging purposes, and individual tests can
        # create their own. Tests may only want to watch a specific port, while a general
        # logger will want to watch more general traffic which can be filtered later.
        return PcapListener(device, bpf_filter, dumpfile, self.__pcap_callback)

    def start_asterisk(self):
        """ This is kept mostly for legacy support.  When the TestCase previously
        used a synchronous, blocking mechanism independent of the twisted
        reactor to spawn Asterisk, this method was called.  Now the Asterisk
        instances are started immediately after the reactor has started.

        Derived methods can still implement this and have it be called when
        the reactor is running, but immediately before instances of Asterisk
        are launched.
        """
        pass

    def __start_asterisk(self):
        """
        Start the instances of Asterisk that were previously created.  See
        create_asterisk.  Note that this should be the first thing called
        when the reactor has started to run
        """
        def __check_success_failure(result):
            """ Make sure the instances started properly """
            for (success, value) in result:
                if not success:
                    logger.error(value)
                    self.stop_reactor()
            return result

        def __perform_pre_checks(result):
            """ Execute the pre-condition checks """
            self.testConditionController.evaluate_pre_checks()
            return result

        def __run_callback(result):
            """ Notify the test that we are running """
            self.run()
            return result

        # Call the method that derived objects can override
        self.start_asterisk()

        # Gather up the deferred objects from each of the instances of Asterisk
        # and wait until all are finished before proceeding
        start_defers = []
        for index, item in enumerate(self.ast):
            logger.info("Starting Asterisk instance %d" % (index + 1))
            temp_defer = self.ast[index].start()
            start_defers.append(temp_defer)

        d = defer.DeferredList(start_defers, consumeErrors=True)
        d.addCallback(__check_success_failure)
        d.addCallback(__perform_pre_checks)
        d.addCallback(__run_callback)

    def stop_asterisk(self):
        """
        Called when the instances of Asterisk are being stopped.  Note that previously,
        this explicitly stopped the Asterisk instances: now they are stopped automatically
        when the reactor is stopped.

        Derived methods can still implement this and have it be called when
        the reactor is running, but immediately before instances of Asterisk
        are stopped.
        """
        pass

    def __stop_asterisk(self):
        """ Stops the instances of Asterisk.

        Stops the instances of Asterisk - called when stop_reactor is called.  This
        returns a deferred object that can be used to be notified when all instances
        of Asterisk have stopped.
         """
        def __check_success_failure(result):
            """ Make sure the instances stopped properly """
            for (success, value) in result:
                if not success:
                    logger.warning(value)
                    # This should already be called when the reactor is being terminated.
                    # If we couldn't stop the instance of Asterisk, there isn't much else to do
                    # here other then complain
            return result

        # Call the overridable method
        self.stop_asterisk()

        self.testConditionController.evaluate_post_checks()

        # Gather up the stopped defers; check success failure of stopping when
        # all instances of Asterisk have stopped
        stop_defers = []
        for index, item in enumerate(self.ast):
            logger.info("Stopping Asterisk instance %d" % (index + 1))
            temp_defer = self.ast[index].stop()
            stop_defers.append(temp_defer)

        d = defer.DeferredList(stop_defers, consumeErrors=True)
        d.addCallback(__check_success_failure)
        return d

    def stop_reactor(self):
        """
        Stop the reactor and cancel the test.
        """
        def __stop_reactor(result):
            """ Called when the Asterisk instances are stopped """
            logger.info("Stopping Reactor")
            if reactor.running:
                try:
                    reactor.stop()
                except twisted.internet.error.ReactorNotRunning:
                    # Something stopped it between our checks - at least we're stopped
                    pass
        if not self.__stopping:
            df = self.__stop_asterisk()
            df.addCallback(__stop_reactor)
            self.__stopping = True

    def __reactor_timeout(self):
        """
        A wrapper function for stop_reactor(), so we know when a reactor timeout
        has occurred.
        """
        logger.warning("Reactor timeout: '%s' seconds" % self.reactor_timeout)
        self.stop_reactor()

    def __run(self):
        """
        Private entry point called when the reactor first starts up.
        This needs to first ensure that Asterisk is fully up and running before
        moving on.
        """
        if (self.ast):
            self.__start_asterisk()
        else:
            # If no instances of Asterisk are needed, go ahead and just run
            self.run()

    def run(self):
        """
        Base implementation of the test execution method, run.  Derived classes
        should override this and start their Asterisk dependent logic from this method.
        Derived classes must call this implementation, as this method provides a fail
        out mechanism in case the test hangs.
        """
        if (self.reactor_timeout > 0):
            self.timeoutId = reactor.callLater(self.reactor_timeout, self.__reactor_timeout)

    def ami_login_error(self, ami):
        """
        Handler for login errors into AMI.  This will stop the test.

        Keyword arguments:
        ami -- The instance of AMI that raised the login error

        """
        logger.error("Error logging into AMI")
        self.stop_reactor()
        return failure.Failure()

    def ami_connect(self, ami):
        """
        Hook method used after create_ami_factory() successfully logs into
        the Asterisk AMI.
        """
        pass

    def __ami_connect(self, ami):
        logger.info("AMI Connect instance %s" % (ami.id + 1))
        self.ami[ami.id] = ami
        self.ami_connect(ami)

    def pcap_callback(self, packet):
        """
        Hook method used to receive captured packets.
        """
        pass

    def __pcap_callback(self, packet):
        self.pcap_callback(packet)

    def handleOriginateFailure(self, reason):
        """
        Convenience callback handler for twisted deferred errors for an AMI originate call.  Derived
        classes can choose to add this handler to originate calls in order to handle them safely when
        they fail.  This will stop the test if called.

        Keyword arguments:
        reason -- The reason the originate failed
        """
        logger.error("Error sending originate:")
        logger.error(reason.getTraceback())
        self.stop_reactor()
        return reason

    def reset_timeout(self):
        """
        Resets the reactor timeout
        """
        if (self.timeoutId != None):
            originalTime = datetime.datetime.fromtimestamp(self.timeoutId.getTime())
            self.timeoutId.reset(self.reactor_timeout)
            newTime = datetime.datetime.fromtimestamp(self.timeoutId.getTime())
            logger.info("Reactor timeout originally scheduled for %s, rescheduled for %s" % (str(originalTime), str(newTime)))

    def handle_condition_failure(self, test_condition):
        """
        Callback handler for condition failures
        """
        if test_condition.pass_expected:
            logger.error("Test Condition %s failed; setting test passed status to False" % test_condition.getName())
            self.passed = False
        else:
            logger.info("Test Condition %s failed but expected failure was set; test status not modified" % test_condition.getName())
